
from python_rag.infra.mysql import get_mysql_connection


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
            cursor.execute(
                """
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
                LIMIT %s
                """,
                (doc_id, limit),
            )
            return cursor.fetchall()
    finally:
        conn.close()