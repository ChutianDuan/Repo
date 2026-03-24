from python_rag.infra.mysql import get_mysql_connection


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
            cursor.execute(
                """
                SELECT id, user_id, filename, mime, sha256, size_bytes,
                       storage_path, status, error_message, created_at, updated_at
                FROM documents
                WHERE id=%s
                """,
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