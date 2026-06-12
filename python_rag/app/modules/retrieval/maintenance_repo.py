import json
from typing import Iterable

from python_rag.app.infra.mysql import get_mysql_connection
from python_rag.app.infra.schema_support import has_column


def _normalize_positive_ints(values: Iterable[int]) -> list[int]:
    normalized = []
    seen = set()
    for value in values or []:
        try:
            item = int(value)
        except (TypeError, ValueError):
            continue
        if item <= 0 or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _decode_meta(row):
    if not row or not row.get("meta_json"):
        return row
    try:
        row["meta_json"] = json.loads(row["meta_json"])
    except Exception:
        pass
    return row


def _vector_job_fields() -> str:
    return ", ".join([
        "id",
        "doc_id",
        "celery_task_id",
        "provider",
        "status",
        "chunk_count",
        "error_message",
        "meta_json",
        "created_at",
        "updated_at",
    ])


def list_chunk_refs_by_doc_id(doc_id: int) -> list[dict]:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, doc_id
                FROM doc_chunks
                WHERE doc_id=%s
                ORDER BY chunk_index ASC
                """,
                (int(doc_id),),
            )
            return cursor.fetchall()
    finally:
        conn.close()


def list_existing_chunk_refs(chunk_ids: Iterable[int]) -> dict[int, int]:
    normalized_ids = _normalize_positive_ints(chunk_ids)
    if not normalized_ids:
        return {}

    placeholders = ", ".join(["%s"] * len(normalized_ids))
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, doc_id
                FROM doc_chunks
                WHERE id IN ({placeholders})
                """.format(placeholders=placeholders),
                tuple(normalized_ids),
            )
            return {int(row["id"]): int(row["doc_id"]) for row in cursor.fetchall()}
    finally:
        conn.close()


def _count_chunk_statuses(doc_id: int, column_name: str) -> dict[str, int]:
    if not has_column("doc_chunks", column_name):
        return {}

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT {column_name} AS status, COUNT(*) AS count
                FROM doc_chunks
                WHERE doc_id=%s
                GROUP BY {column_name}
                """.format(column_name=column_name),
                (int(doc_id),),
            )
            return {
                str(row.get("status") or ""): int(row.get("count") or 0)
                for row in cursor.fetchall()
            }
    finally:
        conn.close()


def get_document_chunk_stats(doc_id: int) -> dict:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS chunk_count
                FROM doc_chunks
                WHERE doc_id=%s
                """,
                (int(doc_id),),
            )
            row = cursor.fetchone() or {}
    finally:
        conn.close()

    return {
        "chunk_count": int(row.get("chunk_count") or 0),
        "embedding_status_counts": _count_chunk_statuses(doc_id, "embedding_status"),
        "vector_index_status_counts": _count_chunk_statuses(doc_id, "vector_index_status"),
    }


def create_vector_index_job(
    doc_id: int,
    celery_task_id: str,
    provider: str = "lancedb",
    status: str = "pending",
    chunk_count: int = 0,
    meta: dict | None = None,
) -> int:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vector_index_jobs (
                    doc_id, celery_task_id, provider, status, chunk_count, meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    int(doc_id),
                    celery_task_id,
                    provider,
                    status,
                    int(chunk_count or 0),
                    json.dumps(meta or {}, ensure_ascii=False),
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def update_vector_index_job_by_task_id(
    celery_task_id: str,
    status: str | None = None,
    chunk_count: int | None = None,
    error_message: str | None = None,
    meta: dict | None = None,
) -> int:
    fields = []
    params = []
    if status is not None:
        fields.append("status=%s")
        params.append(status)
    if chunk_count is not None:
        fields.append("chunk_count=%s")
        params.append(int(chunk_count or 0))
    if error_message is not None:
        fields.append("error_message=%s")
        params.append(error_message)
    if meta is not None:
        fields.append("meta_json=%s")
        params.append(json.dumps(meta, ensure_ascii=False))
    if not fields:
        return 0

    params.append(celery_task_id)
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE vector_index_jobs SET {fields} WHERE celery_task_id=%s".format(
                    fields=", ".join(fields),
                ),
                tuple(params),
            )
            return cursor.rowcount
    finally:
        conn.close()


def get_latest_vector_index_job(doc_id: int):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT {fields}
                FROM vector_index_jobs
                WHERE doc_id=%s
                ORDER BY id DESC
                LIMIT 1
                """.format(fields=_vector_job_fields()),
                (int(doc_id),),
            )
            return _decode_meta(cursor.fetchone())
    finally:
        conn.close()
