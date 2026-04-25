from python_rag.infra.mysql import get_mysql_connection
from python_rag.infra.schema_support import has_column


def create_document_record(user_id, filename, mime, sha256, size_bytes, storage_path, status):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO documents (
                    user_id, filename, mime, sha256, size_bytes, storage_path, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, filename, mime, sha256, size_bytes, storage_path, status),
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


def update_document_status(doc_id, status, error_message=None):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE documents
                SET status=%s, error_message=%s
                WHERE id=%s
                """,
                (status, error_message, doc_id),
            )
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



def _estimate_tokens(text):
    """
    简单估算：
    - 有空格时按 split 词数估算
    - 没空格时按字符数估算
    """
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

    rows = []
    for idx, text in enumerate(chunks):
        rows.append(
            (
                doc_id,
                idx,
                text,
                _estimate_tokens(text),
            )
        )

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO doc_chunks (
                    doc_id, chunk_index, text, tokens_est
                ) VALUES (%s, %s, %s, %s)
                """,
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
                    id,
                    doc_id,
                    chunk_index,
                    text AS content,
                    tokens_est,
                    created_at
                FROM doc_chunks
                WHERE doc_id=%s
                ORDER BY chunk_index ASC
            """
            params = [doc_id]
            if limit is not None:
                sql += " LIMIT %s"
                params.append(limit)

            cursor.execute(sql, tuple(params))
            return cursor.fetchall()
    finally:
        conn.close()
