from typing import Iterable

from python_rag.app.infra.mysql import get_mysql_connection
from python_rag.app.infra.schema_support import has_column


DOCUMENT_INDEX_NOT_INDEXED = "not_indexed"
DOCUMENT_INDEX_INDEXING = "indexing"
DOCUMENT_INDEX_INDEXED = "indexed"
DOCUMENT_INDEX_FAILED = "failed"
CHUNK_EMBEDDING_PENDING = "pending"
CHUNK_EMBEDDING_EMBEDDED = "embedded"
CHUNK_EMBEDDING_FAILED = "failed"
CHUNK_VECTOR_PENDING = "pending"
CHUNK_VECTOR_INDEXED = "indexed"
CHUNK_VECTOR_FAILED = "failed"


def _documents_has_index_status() -> bool:
    return has_column("documents", "index_status")


def _chunks_has_embedding_status() -> bool:
    return has_column("doc_chunks", "embedding_status")


def _chunks_has_vector_index_status() -> bool:
    return has_column("doc_chunks", "vector_index_status")


def _chunk_select_fields(prefix: str = ""):
    base = [
        f"{prefix}id",
        f"{prefix}doc_id",
        f"{prefix}chunk_index",
        f"{prefix}text AS content",
        f"{prefix}tokens_est",
        f"{prefix}created_at",
    ]
    if _chunks_has_embedding_status():
        base.append(f"{prefix}embedding_status")
    if _chunks_has_vector_index_status():
        base.append(f"{prefix}vector_index_status")
    return base


def create_document_record(user_id, filename, mime, sha256, size_bytes, storage_path, status):
    fields = [
        "user_id",
        "filename",
        "mime",
        "sha256",
        "size_bytes",
        "storage_path",
        "status",
    ]
    params = [user_id, filename, mime, sha256, size_bytes, storage_path, status]
    if _documents_has_index_status():
        fields.append("index_status")
        params.append(DOCUMENT_INDEX_NOT_INDEXED)

    placeholders = ", ".join(["%s"] * len(fields))
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO documents ({fields})
                VALUES ({placeholders})
                """.format(fields=", ".join(fields), placeholders=placeholders),
                tuple(params),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_document_by_id(doc_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            fields = [
                "id",
                "user_id",
                "filename",
                "mime",
                "sha256",
                "size_bytes",
                "storage_path",
                "status",
                "error_message",
                "created_at",
            ]
            if _documents_has_index_status():
                fields.append("index_status")
            if has_column("documents", "updated_at"):
                fields.append("updated_at")
            cursor.execute(
                """
                SELECT {fields}
                FROM documents
                WHERE id=%s
                """.format(fields=", ".join(fields)),
                (doc_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def list_documents(user_id=None, status=None, limit=100):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            conditions = []
            params = []
            updated_at_field = (
                "d.updated_at"
                if has_column("documents", "updated_at")
                else "d.created_at AS updated_at"
            )
            has_index_status = _documents_has_index_status()
            index_status_field = (
                "d.index_status AS index_status"
                if has_index_status
                else "di.status AS index_status"
            )

            if user_id is not None:
                conditions.append("d.user_id=%s")
                params.append(user_id)
            if status:
                normalized_status = str(status).strip().lower()
                if normalized_status in ("ready", "indexed"):
                    if has_index_status:
                        conditions.append("d.index_status=%s")
                        params.append(DOCUMENT_INDEX_INDEXED)
                    else:
                        conditions.append("d.status=%s")
                        params.append("READY")
                else:
                    conditions.append("d.status=%s")
                    params.append(status)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            sql = """
                SELECT
                    d.id,
                    d.user_id,
                    d.filename,
                    d.mime,
                    d.sha256,
                    d.size_bytes,
                    d.storage_path,
                    d.status,
                    {index_status_field},
                    d.error_message,
                    d.created_at,
                    {updated_at_field},
                    (
                        SELECT COUNT(*)
                        FROM doc_chunks c
                        WHERE c.doc_id = d.id
                    ) AS chunk_count,
                    di.status AS legacy_index_status
                FROM documents d
                LEFT JOIN document_indexes di ON di.doc_id = d.id
                {where_clause}
                ORDER BY d.created_at DESC, d.id DESC
                LIMIT %s
            """.format(
                where_clause=where_clause,
                updated_at_field=updated_at_field,
                index_status_field=index_status_field,
            )
            params.append(max(1, int(limit or 100)))

            cursor.execute(sql, tuple(params))
            return cursor.fetchall()
    finally:
        conn.close()


def list_ready_document_ids(user_id=None, embedding_model=None, limit=1000):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            params = []
            has_index_status = _documents_has_index_status()
            if has_index_status:
                conditions = ["d.index_status=%s"]
                params.append(DOCUMENT_INDEX_INDEXED)
                join_clause = (
                    "INNER JOIN document_indexes di ON di.doc_id = d.id"
                    if embedding_model
                    else ""
                )
            else:
                conditions = ["d.status='READY'", "di.status='READY'"]
                join_clause = "INNER JOIN document_indexes di ON di.doc_id = d.id"

            if user_id is not None:
                conditions.append("d.user_id=%s")
                params.append(user_id)
            if embedding_model:
                conditions.append("di.embedding_model=%s")
                params.append(embedding_model)

            sql = """
                SELECT d.id
                FROM documents d
                {join_clause}
                WHERE {where_clause}
                ORDER BY d.created_at DESC, d.id DESC
                LIMIT %s
            """.format(join_clause=join_clause, where_clause=" AND ".join(conditions))
            params.append(max(1, int(limit or 1000)))

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return [row["id"] for row in rows]
    finally:
        conn.close()


def update_document_status(doc_id, status, error_message=None, index_status=None):
    fields = ["status=%s", "error_message=%s"]
    params = [status, error_message]
    if index_status is not None and _documents_has_index_status():
        fields.append("index_status=%s")
        params.append(index_status)
    params.append(doc_id)

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE documents SET {fields} WHERE id=%s".format(fields=", ".join(fields)),
                tuple(params),
            )
    finally:
        conn.close()


def update_document_index_status(doc_id, index_status, error_message=None):
    if not _documents_has_index_status():
        return 0

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE documents
                SET index_status=%s, error_message=%s
                WHERE id=%s
                """,
                (index_status, error_message, doc_id),
            )
            return cursor.rowcount
    finally:
        conn.close()


def upsert_document_index(
        doc_id,
        index_type,
        embedding_model,
        dimension,
        index_path,
        mapping_path,
        chunk_count,
        status: str = "READY",
):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            update_fields = [
                "index_type=VALUES(index_type)",
                "embedding_model=VALUES(embedding_model)",
                "dimension=VALUES(dimension)",
                "index_path=VALUES(index_path)",
                "mapping_path=VALUES(mapping_path)",
                "chunk_count=VALUES(chunk_count)",
                "status=VALUES(status)",
            ]
            if has_column("document_indexes", "updated_at"):
                update_fields.append("updated_at=CURRENT_TIMESTAMP")
            cursor.execute(
                """
                INSERT INTO document_indexes (
                    doc_id, index_type, embedding_model, dimension,
                    index_path, mapping_path, chunk_count, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    {update_fields}
                """.format(update_fields=",\n                    ".join(update_fields)),
                (
                    doc_id,
                    index_type,
                    embedding_model,
                    dimension,
                    index_path,
                    mapping_path,
                    chunk_count,
                    status,
                ),
            )
    finally:
        conn.close()


def get_document_index_by_doc_id(doc_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            fields = [
                "doc_id",
                "index_type",
                "embedding_model",
                "dimension",
                "index_path",
                "mapping_path",
                "chunk_count",
                "status",
                "created_at",
            ]
            if has_column("document_indexes", "updated_at"):
                fields.append("updated_at")
            cursor.execute(
                """
                SELECT {fields}
                FROM document_indexes
                WHERE doc_id=%s
                """.format(fields=", ".join(fields)),
                (doc_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def delete_document_by_id(doc_id):
    conn = get_mysql_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM citations WHERE doc_id=%s",
                (doc_id,),
            )
            deleted_citations = cursor.rowcount

            cursor.execute(
                "DELETE FROM document_indexes WHERE doc_id=%s",
                (doc_id,),
            )
            deleted_indexes = cursor.rowcount

            cursor.execute(
                "DELETE FROM doc_chunks WHERE doc_id=%s",
                (doc_id,),
            )
            deleted_chunks = cursor.rowcount

            cursor.execute(
                "DELETE FROM documents WHERE id=%s",
                (doc_id,),
            )
            deleted_documents = cursor.rowcount

        conn.commit()
        return {
            "deleted_documents": deleted_documents,
            "deleted_indexes": deleted_indexes,
            "deleted_chunks": deleted_chunks,
            "deleted_citations": deleted_citations,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _estimate_tokens(text):
    text = (text or "").strip()
    if not text:
        return 0

    word_count = len(text.split())
    if word_count > 1:
        return word_count

    return len(text)


def delete_chunks_by_doc_id(doc_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM doc_chunks WHERE doc_id=%s",
                (doc_id,),
            )
            return cursor.rowcount
    finally:
        conn.close()


def bulk_insert_chunks(doc_id, chunks):
    if not chunks:
        return 0

    fields = ["doc_id", "chunk_index", "text", "tokens_est"]
    if _chunks_has_embedding_status():
        fields.append("embedding_status")
    if _chunks_has_vector_index_status():
        fields.append("vector_index_status")

    rows = []
    for idx, text in enumerate(chunks):
        row = [doc_id, idx, text, _estimate_tokens(text)]
        if _chunks_has_embedding_status():
            row.append(CHUNK_EMBEDDING_PENDING)
        if _chunks_has_vector_index_status():
            row.append(CHUNK_VECTOR_PENDING)
        rows.append(tuple(row))

    placeholders = ", ".join(["%s"] * len(fields))
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO doc_chunks ({fields})
                VALUES ({placeholders})
                """.format(fields=", ".join(fields), placeholders=placeholders),
                rows,
            )
            return cursor.rowcount
    finally:
        conn.close()


def list_chunks_by_doc_id(doc_id, limit=200):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT
                    {fields}
                FROM doc_chunks
                WHERE doc_id=%s
                ORDER BY chunk_index ASC
            """.format(fields=",\n                    ".join(_chunk_select_fields()))
            params = [doc_id]
            if limit is not None:
                sql += " LIMIT %s"
                params.append(limit)

            cursor.execute(sql, tuple(params))
            return cursor.fetchall()
    finally:
        conn.close()


def list_chunks_by_ids(chunk_ids: Iterable[int]):
    normalized_ids = []
    seen = set()
    for value in chunk_ids or []:
        try:
            chunk_id = int(value)
        except (TypeError, ValueError):
            continue
        if chunk_id <= 0 or chunk_id in seen:
            continue
        seen.add(chunk_id)
        normalized_ids.append(chunk_id)

    if not normalized_ids:
        return []

    placeholders = ", ".join(["%s"] * len(normalized_ids))
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    {fields}
                FROM doc_chunks
                WHERE id IN ({placeholders})
                """.format(
                    fields=",\n                    ".join(_chunk_select_fields()),
                    placeholders=placeholders,
                ),
                tuple(normalized_ids),
            )
            return cursor.fetchall()
    finally:
        conn.close()


def update_chunks_index_status(
    doc_id,
    chunk_ids=None,
    embedding_status=None,
    vector_index_status=None,
):
    fields = []
    params = []
    if embedding_status is not None and _chunks_has_embedding_status():
        fields.append("embedding_status=%s")
        params.append(embedding_status)
    if vector_index_status is not None and _chunks_has_vector_index_status():
        fields.append("vector_index_status=%s")
        params.append(vector_index_status)
    if not fields:
        return 0

    conditions = ["doc_id=%s"]
    params.append(doc_id)
    normalized_chunk_ids = []
    for value in chunk_ids or []:
        try:
            chunk_id = int(value)
        except (TypeError, ValueError):
            continue
        if chunk_id > 0:
            normalized_chunk_ids.append(chunk_id)
    if normalized_chunk_ids:
        conditions.append("id IN ({0})".format(", ".join(["%s"] * len(normalized_chunk_ids))))
        params.extend(normalized_chunk_ids)

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE doc_chunks SET {fields} WHERE {conditions}".format(
                    fields=", ".join(fields),
                    conditions=" AND ".join(conditions),
                ),
                tuple(params),
            )
            return cursor.rowcount
    finally:
        conn.close()
