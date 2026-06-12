import re
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, List, Optional

from python_rag.app.core.config import LANCEDB_PATH, LANCEDB_TABLE
from python_rag.app.core.error_codes import ERR_INTERNAL_ERROR
from python_rag.app.core.errors import AppError
from python_rag.app.retrieval.vector_store.base import VectorRecord, VectorSearchHit


def _import_lancedb():
    try:
        import lancedb
    except Exception as exc:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "lancedb dependency is not available: {0}".format(exc),
            http_status=500,
        ) from exc
    return lancedb


def _import_numpy():
    try:
        import numpy as np
    except Exception as exc:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "numpy dependency is not available for vector search: {0}".format(exc),
            http_status=500,
        ) from exc
    return np


def _normalize_vector(vector: Any) -> List[float]:
    np = _import_numpy()
    array = np.asarray(vector, dtype="float32").reshape(-1)
    return [float(item) for item in array]


def _normalize_document_ids(document_ids: Optional[Iterable[int]]) -> List[int]:
    normalized = []
    seen = set()
    for value in document_ids or []:
        try:
            document_id = int(value)
        except (TypeError, ValueError):
            continue
        if document_id <= 0 or document_id in seen:
            continue
        seen.add(document_id)
        normalized.append(document_id)
    return normalized


def _distance_to_score(distance: Any) -> float:
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return 0.0
    if value < 0:
        return 0.0
    return 1.0 / (1.0 + value)


def _directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0

    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _safe_label(value: Optional[str]) -> str:
    label = (value or "").strip()
    if not label:
        return ""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("._")


class LanceDBVectorStore:
    def __init__(self, uri: Optional[str] = None, table_name: Optional[str] = None):
        self.uri = uri or LANCEDB_PATH
        self.table_name = table_name or LANCEDB_TABLE

    def _connect(self):
        Path(self.uri).mkdir(parents=True, exist_ok=True)
        return _import_lancedb().connect(self.uri)

    def _table_exists(self, db) -> bool:
        try:
            return self.table_name in set(db.table_names())
        except Exception:
            try:
                db.open_table(self.table_name)
                return True
            except Exception:
                return False

    def _open_table(self, required: bool = True):
        db = self._connect()
        if self._table_exists(db):
            return db.open_table(self.table_name)
        if required:
            raise AppError(
                ERR_INTERNAL_ERROR,
                "LanceDB table not found: {0}".format(self.table_name),
                http_status=500,
            )
        return None

    def table_exists(self) -> bool:
        db = self._connect()
        return self._table_exists(db)

    @staticmethod
    def _table_to_rows(table, columns: Optional[List[str]] = None) -> List[dict]:
        columns = columns or []
        rows = None
        if hasattr(table, "to_pandas"):
            for kwargs in ({"columns": columns} if columns else {}, {}):
                try:
                    dataframe = table.to_pandas(**kwargs)
                    rows = dataframe.to_dict("records")
                    break
                except TypeError:
                    continue
                except Exception:
                    if kwargs:
                        continue
                    raise
        if rows is None and hasattr(table, "to_arrow"):
            for kwargs in ({"columns": columns} if columns else {}, {}):
                try:
                    arrow_table = table.to_arrow(**kwargs)
                    rows = arrow_table.to_pylist()
                    break
                except TypeError:
                    continue
                except Exception:
                    if kwargs:
                        continue
                    raise
        if rows is None:
            raise AppError(
                ERR_INTERNAL_ERROR,
                "LanceDB table scan is not supported by installed lancedb version",
                http_status=500,
            )

        if not columns:
            return rows
        allowed = set(columns)
        return [
            {key: value for key, value in row.items() if key in allowed}
            for row in rows
        ]

    def _count_rows(self, table) -> int:
        if hasattr(table, "count_rows"):
            try:
                return int(table.count_rows())
            except Exception:
                pass
        return len(self._table_to_rows(table, columns=["chunk_id"]))

    def list_vector_refs(
        self,
        document_ids: Optional[Iterable[int]] = None,
        limit: Optional[int] = None,
    ) -> List[dict]:
        table = self._open_table(required=False)
        if table is None:
            return []

        normalized_document_ids = set(_normalize_document_ids(document_ids))
        rows = self._table_to_rows(
            table,
            columns=[
                "chunk_id",
                "document_id",
                "chunk_index",
                "content_hash",
                "status",
            ],
        )

        refs = []
        for row in rows:
            try:
                document_id = int(row.get("document_id"))
                chunk_id = int(row.get("chunk_id"))
                chunk_index = int(row.get("chunk_index"))
            except (TypeError, ValueError):
                continue
            if normalized_document_ids and document_id not in normalized_document_ids:
                continue
            refs.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "content_hash": row.get("content_hash") or "",
                    "status": row.get("status") or "",
                }
            )
            if limit is not None and len(refs) >= int(limit):
                break
        return refs

    def capacity(self, document_sample_limit: int = 20) -> dict:
        path = Path(self.uri)
        table = self._open_table(required=False)
        table_exists = table is not None
        row_count = 0
        dimension = 0
        status_counts = {}
        top_documents = []
        document_count = 0

        if table_exists:
            try:
                row_count = self._count_rows(table)
            except Exception:
                row_count = 0

            rows = self._table_to_rows(
                table,
                columns=["document_id", "status", "vector"],
            )
            if row_count <= 0:
                row_count = len(rows)
            document_counter = Counter()
            status_counter = Counter()
            for row in rows:
                try:
                    document_counter[int(row.get("document_id"))] += 1
                except (TypeError, ValueError):
                    pass
                status = row.get("status") or ""
                if status:
                    status_counter[str(status)] += 1
                if dimension <= 0 and row.get("vector") is not None:
                    try:
                        dimension = len(_normalize_vector(row.get("vector")))
                    except Exception:
                        dimension = 0
            document_count = len(document_counter)
            status_counts = dict(status_counter)
            top_documents = [
                {"doc_id": doc_id, "vector_count": count}
                for doc_id, count in document_counter.most_common(
                    max(1, int(document_sample_limit or 20))
                )
            ]

        return {
            "index_type": "lancedb",
            "uri": self.uri,
            "table_name": self.table_name,
            "table_exists": table_exists,
            "row_count": row_count,
            "vector_count": row_count,
            "document_count": document_count,
            "dimension": dimension,
            "status_counts": status_counts,
            "top_documents": top_documents,
            "disk_bytes": _directory_size_bytes(path),
            "path_exists": path.exists(),
        }

    def delete_chunk_ids(self, chunk_ids: Iterable[int]) -> int:
        normalized = []
        seen = set()
        for value in chunk_ids or []:
            try:
                chunk_id = int(value)
            except (TypeError, ValueError):
                continue
            if chunk_id <= 0 or chunk_id in seen:
                continue
            seen.add(chunk_id)
            normalized.append(chunk_id)

        if not normalized:
            return 0

        table = self._open_table(required=False)
        if table is None:
            return 0

        deleted_count = 0
        batch_size = 500
        for start in range(0, len(normalized), batch_size):
            batch = normalized[start:start + batch_size]
            table.delete(
                "chunk_id IN ({0})".format(
                    ", ".join(str(item) for item in batch)
                )
            )
            deleted_count += len(batch)
        return deleted_count

    def backup(self, backup_dir: Optional[str] = None, label: Optional[str] = None) -> dict:
        source = Path(self.uri).resolve()
        if not source.exists() or not source.is_dir():
            raise AppError(
                ERR_INTERNAL_ERROR,
                "LanceDB path not found: {0}".format(source),
                http_status=404,
            )

        timestamp = time.strftime("%Y%m%d%H%M%S")
        suffix = _safe_label(label)
        backup_name = "{0}_{1}".format(self.table_name, timestamp)
        if suffix:
            backup_name = "{0}_{1}".format(backup_name, suffix)

        target_root = Path(backup_dir).resolve() if backup_dir else source.parent / "lancedb_backups"
        target_root.mkdir(parents=True, exist_ok=True)
        target = target_root / backup_name
        if target.exists():
            raise AppError(
                ERR_INTERNAL_ERROR,
                "LanceDB backup target already exists: {0}".format(target),
                http_status=409,
            )

        shutil.copytree(source, target)
        return {
            "index_type": "lancedb",
            "uri": self.uri,
            "table_name": self.table_name,
            "backup_path": str(target),
            "backup_bytes": _directory_size_bytes(target),
            "created_at": timestamp,
        }

    def restore(self, backup_path: str, overwrite: bool = False) -> dict:
        source = Path(backup_path).resolve()
        if not source.exists() or not source.is_dir():
            raise AppError(
                ERR_INTERNAL_ERROR,
                "LanceDB backup path not found: {0}".format(source),
                http_status=404,
            )

        target = Path(self.uri).resolve()
        safety_backup = None
        target_exists = target.exists()
        target_has_content = target_exists and (not target.is_dir() or any(target.iterdir()))
        if target_has_content and not overwrite:
            raise AppError(
                ERR_INTERNAL_ERROR,
                "LanceDB path is not empty; pass overwrite=true to restore",
                http_status=409,
            )

        if target_has_content:
            safety_backup = target.parent / "{0}.pre_restore_{1}".format(
                target.name,
                time.strftime("%Y%m%d%H%M%S"),
            )
            target.rename(safety_backup)

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(source, target, dirs_exist_ok=True)
        except Exception:
            if safety_backup and safety_backup.exists():
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                safety_backup.rename(target)
            raise

        return {
            "index_type": "lancedb",
            "uri": self.uri,
            "table_name": self.table_name,
            "restored_from": str(source),
            "restored_bytes": _directory_size_bytes(target),
            "pre_restore_backup_path": str(safety_backup) if safety_backup else None,
            "overwritten": bool(target_has_content),
        }

    @staticmethod
    def _record_to_dict(record: VectorRecord) -> dict:
        return {
            "chunk_id": int(record.chunk_id),
            "document_id": int(record.document_id),
            "chunk_index": int(record.chunk_index),
            "title": record.title or "",
            "content_hash": record.content_hash or "",
            "status": record.status or "indexed",
            "vector": _normalize_vector(record.vector),
        }

    def upsert(self, records: List[VectorRecord]) -> dict:
        rows = [self._record_to_dict(record) for record in records]
        if not rows:
            return {
                "index_type": "lancedb",
                "uri": self.uri,
                "table_name": self.table_name,
                "dimension": 0,
                "chunk_count": 0,
                "created": False,
            }

        db = self._connect()
        dimension = len(rows[0]["vector"])
        created = False
        if not self._table_exists(db):
            db.create_table(self.table_name, data=rows)
            created = True
        else:
            table = db.open_table(self.table_name)
            document_ids = sorted({int(row["document_id"]) for row in rows})
            for document_id in document_ids:
                table.delete("document_id = {0}".format(document_id))
            try:
                (
                    table.merge_insert("chunk_id")
                    .when_matched_update_all()
                    .when_not_matched_insert_all()
                    .execute(rows)
                )
            except Exception:
                table.add(rows)

        return {
            "index_type": "lancedb",
            "uri": self.uri,
            "table_name": self.table_name,
            "dimension": dimension,
            "chunk_count": len(rows),
            "created": created,
        }

    def delete_document(self, document_id: int) -> int:
        table = self._open_table(required=False)
        if table is None:
            return 0
        table.delete("document_id = {0}".format(int(document_id)))
        return 1

    def _where_clause(self, document_ids: Optional[Iterable[int]]) -> str:
        parts = ["status = 'indexed'"]
        normalized_document_ids = _normalize_document_ids(document_ids)
        if normalized_document_ids:
            parts.append(
                "document_id IN ({0})".format(
                    ", ".join(str(item) for item in normalized_document_ids)
                )
            )
        return " AND ".join(parts)

    def search(
        self,
        query_vector: Any,
        top_k: int,
        document_ids: Optional[Iterable[int]] = None,
    ) -> List[VectorSearchHit]:
        if top_k <= 0:
            return []

        table = self._open_table(required=False)
        if table is None:
            return []

        query = table.search(_normalize_vector(query_vector))
        if hasattr(query, "metric"):
            query = query.metric("cosine")
        elif hasattr(query, "distance_type"):
            query = query.distance_type("cosine")
        query = query.where(self._where_clause(document_ids)).limit(int(top_k))
        if hasattr(query, "select"):
            query = query.select([
                "chunk_id",
                "document_id",
                "chunk_index",
                "title",
                "content_hash",
                "status",
                "_distance",
            ])

        rows = query.to_list()
        hits = []
        for rank, row in enumerate(rows, start=1):
            distance = row.get("_distance")
            hits.append(
                VectorSearchHit(
                    chunk_id=int(row.get("chunk_id")),
                    document_id=int(row.get("document_id")),
                    chunk_index=int(row.get("chunk_index")),
                    title=row.get("title") or "",
                    content_hash=row.get("content_hash") or "",
                    status=row.get("status") or "",
                    score=_distance_to_score(distance),
                    distance=float(distance) if distance is not None else None,
                    rank=rank,
                )
            )
        return hits
