import uuid
from collections import Counter
from typing import Any, Iterable, Optional

from python_rag.app.core.error_codes import (
    ERR_CELERY_ERROR,
    ERR_DOCUMENT_NOT_FOUND,
    ERR_INDEX_NOT_FOUND,
    ERR_INVALID_REQUEST,
    TaskState,
)
from python_rag.app.core.errors import AppError
from python_rag.app.core.logger import logger
from python_rag.app.modules.documents.repo import (
    get_document_by_id,
    get_document_index_by_doc_id,
)
from python_rag.app.modules.retrieval.maintenance_repo import (
    create_vector_index_job,
    get_document_chunk_stats,
    get_latest_vector_index_job,
    list_chunk_refs_by_doc_id,
    list_existing_chunk_refs,
    update_vector_index_job_by_task_id,
)
from python_rag.app.modules.tasks.repo import create_task_record, update_task_record
from python_rag.app.retrieval.indexing_service import (
    get_vector_store,
    search_vectors,
    upsert_document_chunk_vectors,
)


ORPHAN_SAMPLE_LIMIT = 100


def upsert_chunk_vectors(document, chunk_rows, vectors):
    return upsert_document_chunk_vectors(
        document=document,
        chunk_rows=chunk_rows,
        vectors=vectors,
    )


def search_lancedb_index(query_vector: Any, top_k: int, doc_ids: Optional[Iterable[int]] = None):
    hits = search_vectors(
        query_vector=query_vector,
        top_k=top_k,
        document_ids=doc_ids,
    )
    return [
        {
            "doc_id": hit.document_id,
            "chunk_id": hit.chunk_id,
            "chunk_index": hit.chunk_index,
            "title": hit.title,
            "content_hash": hit.content_hash,
            "status": hit.status,
            "score": hit.score,
            "lancedb_score": hit.score,
            "lancedb_distance": hit.distance,
            "lancedb_rank": hit.rank,
        }
        for hit in hits
    ]


def _lancedb_store():
    return get_vector_store("lancedb")


def _to_iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _format_document(row):
    if not row:
        return None
    return {
        "doc_id": int(row["id"]),
        "user_id": row.get("user_id"),
        "filename": row.get("filename"),
        "status": row.get("status"),
        "index_status": row.get("index_status"),
        "error_message": row.get("error_message"),
        "created_at": _to_iso(row.get("created_at")),
        "updated_at": _to_iso(row.get("updated_at")),
    }


def _format_document_index(row):
    if not row:
        return None
    return {
        "doc_id": row.get("doc_id"),
        "index_type": row.get("index_type"),
        "embedding_model": row.get("embedding_model"),
        "dimension": row.get("dimension"),
        "index_path": row.get("index_path"),
        "mapping_path": row.get("mapping_path"),
        "chunk_count": row.get("chunk_count"),
        "status": row.get("status"),
        "created_at": _to_iso(row.get("created_at")),
        "updated_at": _to_iso(row.get("updated_at")),
    }


def _format_vector_job(row):
    if not row:
        return None
    return {
        "id": row.get("id"),
        "doc_id": row.get("doc_id"),
        "task_id": row.get("celery_task_id"),
        "provider": row.get("provider"),
        "status": row.get("status"),
        "chunk_count": row.get("chunk_count"),
        "error_message": row.get("error_message"),
        "meta": row.get("meta_json"),
        "created_at": _to_iso(row.get("created_at")),
        "updated_at": _to_iso(row.get("updated_at")),
    }


def _count_statuses(vector_refs: list[dict]) -> dict[str, int]:
    counter = Counter()
    for ref in vector_refs:
        status = ref.get("status") or ""
        if status:
            counter[str(status)] += 1
    return dict(counter)


def _build_health(capacity, chunk_stats, missing_chunk_ids, orphan_chunk_ids):
    reasons = []
    if not capacity.get("table_exists"):
        reasons.append("lancedb_table_missing")

    chunk_count = int(chunk_stats.get("chunk_count") or 0)
    if chunk_count <= 0:
        reasons.append("document_has_no_chunks")

    if missing_chunk_ids:
        reasons.append("missing_vectors")
    if orphan_chunk_ids:
        reasons.append("orphan_vectors")

    vector_status_counts = chunk_stats.get("vector_index_status_counts") or {}
    if vector_status_counts:
        indexed_count = int(vector_status_counts.get("indexed") or 0)
        if chunk_count > 0 and indexed_count != chunk_count:
            reasons.append("chunk_status_not_fully_indexed")

    if not reasons:
        return {"state": "ready", "healthy": True, "reasons": []}
    if reasons == ["document_has_no_chunks"]:
        return {"state": "empty", "healthy": False, "reasons": reasons}
    return {"state": "degraded", "healthy": False, "reasons": reasons}


def get_lancedb_capacity(document_sample_limit: int = 20):
    return _lancedb_store().capacity(document_sample_limit=document_sample_limit)


def get_lancedb_index_status(doc_id: Optional[int] = None):
    store = _lancedb_store()
    capacity = store.capacity()
    result = {
        "provider": "lancedb",
        "status": "ready" if capacity.get("table_exists") else "missing",
        "healthy": bool(capacity.get("table_exists")),
        "capacity": capacity,
    }
    if doc_id is None:
        return result

    doc = get_document_by_id(int(doc_id))
    if not doc:
        raise AppError(ERR_DOCUMENT_NOT_FOUND, "document not found", http_status=404)

    chunk_stats = get_document_chunk_stats(int(doc_id))
    chunk_refs = list_chunk_refs_by_doc_id(int(doc_id))
    db_chunk_ids = {int(row["id"]) for row in chunk_refs}
    vector_refs = store.list_vector_refs(document_ids=[int(doc_id)])
    vector_chunk_ids = {int(ref["chunk_id"]) for ref in vector_refs}
    missing_chunk_ids = sorted(db_chunk_ids - vector_chunk_ids)
    orphan_chunk_ids = sorted(vector_chunk_ids - db_chunk_ids)
    health = _build_health(capacity, chunk_stats, missing_chunk_ids, orphan_chunk_ids)

    result.update(
        {
            "status": health["state"],
            "healthy": health["healthy"],
            "health": health,
            "document": _format_document(doc),
            "document_index": _format_document_index(
                get_document_index_by_doc_id(int(doc_id))
            ),
            "chunks": chunk_stats,
            "lancedb": {
                "doc_id": int(doc_id),
                "vector_count": len(vector_refs),
                "status_counts": _count_statuses(vector_refs),
            },
            "consistency": {
                "expected_chunk_count": len(db_chunk_ids),
                "actual_vector_count": len(vector_refs),
                "missing_vector_count": len(missing_chunk_ids),
                "orphan_vector_count": len(orphan_chunk_ids),
                "missing_chunk_ids": missing_chunk_ids[:ORPHAN_SAMPLE_LIMIT],
                "orphan_chunk_ids": orphan_chunk_ids[:ORPHAN_SAMPLE_LIMIT],
                "sample_limit": ORPHAN_SAMPLE_LIMIT,
            },
            "latest_vector_index_job": _format_vector_job(
                get_latest_vector_index_job(int(doc_id))
            ),
        }
    )
    return result


def submit_lancedb_document_rebuild(doc_id: int):
    doc_id = int(doc_id)
    doc = get_document_by_id(doc_id)
    if not doc:
        raise AppError(ERR_DOCUMENT_NOT_FOUND, "document not found", http_status=404)

    chunk_stats = get_document_chunk_stats(doc_id)
    chunk_count = int(chunk_stats.get("chunk_count") or 0)
    if chunk_count <= 0:
        raise AppError(ERR_INDEX_NOT_FOUND, "document chunks not found", http_status=404)

    celery_task_id = str(uuid.uuid4())
    meta = {
        "stage": "queued",
        "operation": "rebuild_lancedb_index",
        "doc_id": doc_id,
        "provider": "lancedb",
        "chunk_count": chunk_count,
    }

    try:
        db_task_id = create_task_record(
            celery_task_id=celery_task_id,
            task_type="rebuild_lancedb_index",
            entity_type="document",
            entity_id=doc_id,
            state=TaskState.PENDING,
            progress=0,
            meta=meta,
        )
        try:
            vector_job_id = create_vector_index_job(
                doc_id=doc_id,
                celery_task_id=celery_task_id,
                provider="lancedb",
                status="pending",
                chunk_count=chunk_count,
                meta=meta,
            )
        except Exception as exc:
            update_task_record(
                celery_task_id=celery_task_id,
                state=TaskState.FAILURE,
                progress=100,
                meta={**meta, "stage": "vector_job_record_failed"},
                error=str(exc),
            )
            raise

        try:
            from python_rag.app.tasks.index_tasks import build_embedding_task

            build_embedding_task.apply_async(
                kwargs={"doc_id": doc_id},
                task_id=celery_task_id,
            )
        except Exception as exc:
            update_task_record(
                celery_task_id=celery_task_id,
                state=TaskState.FAILURE,
                progress=100,
                meta={**meta, "stage": "queue_failed"},
                error=str(exc),
            )
            update_vector_index_job_by_task_id(
                celery_task_id,
                status="failed",
                error_message=str(exc),
                meta={**meta, "stage": "queue_failed"},
            )
            raise

        return {
            "db_task_id": db_task_id,
            "vector_job_id": vector_job_id,
            "task_id": celery_task_id,
            "state": TaskState.PENDING,
            "status_url": "/internal/tasks/{0}".format(celery_task_id),
            "vector_status_url": "/internal/lancedb/status?doc_id={0}".format(doc_id),
            "doc_id": doc_id,
            "chunk_count": chunk_count,
        }
    except AppError:
        raise
    except Exception as exc:
        logger.exception("submit_lancedb_document_rebuild failed doc_id=%s", doc_id)
        raise AppError(
            ERR_CELERY_ERROR,
            "submit_lancedb_document_rebuild failed: {0}".format(exc),
        )


def cleanup_lancedb_orphan_vectors(dry_run: bool = True, limit: int = 100000):
    limit = int(limit or 0)
    if limit <= 0:
        raise AppError(ERR_INVALID_REQUEST, "limit must be positive")

    store = _lancedb_store()
    vector_refs = store.list_vector_refs(limit=limit)
    existing_refs = list_existing_chunk_refs(ref.get("chunk_id") for ref in vector_refs)
    orphans = []
    for ref in vector_refs:
        try:
            chunk_id = int(ref.get("chunk_id"))
            vector_doc_id = int(ref.get("document_id"))
        except (TypeError, ValueError):
            continue

        db_doc_id = existing_refs.get(chunk_id)
        if db_doc_id is None:
            reason = "chunk_missing"
        elif int(db_doc_id) != vector_doc_id:
            reason = "document_mismatch"
        else:
            continue

        orphans.append(
            {
                "chunk_id": chunk_id,
                "vector_doc_id": vector_doc_id,
                "db_doc_id": db_doc_id,
                "reason": reason,
            }
        )

    orphan_chunk_ids = sorted({item["chunk_id"] for item in orphans})
    deleted_count = 0
    if not dry_run and orphan_chunk_ids:
        deleted_count = store.delete_chunk_ids(orphan_chunk_ids)

    return {
        "provider": "lancedb",
        "dry_run": bool(dry_run),
        "scanned_vector_count": len(vector_refs),
        "scan_limit": limit,
        "limit_reached": len(vector_refs) >= limit,
        "orphan_count": len(orphan_chunk_ids),
        "deleted_count": deleted_count,
        "orphan_chunk_ids": orphan_chunk_ids[:ORPHAN_SAMPLE_LIMIT],
        "orphans": orphans[:ORPHAN_SAMPLE_LIMIT],
        "sample_limit": ORPHAN_SAMPLE_LIMIT,
    }


def backup_lancedb_index(backup_dir: Optional[str] = None, label: Optional[str] = None):
    return _lancedb_store().backup(backup_dir=backup_dir, label=label)


def restore_lancedb_index(backup_path: str, overwrite: bool = False):
    if not backup_path or not str(backup_path).strip():
        raise AppError(ERR_INVALID_REQUEST, "backup_path is required")
    return _lancedb_store().restore(backup_path=backup_path, overwrite=overwrite)
