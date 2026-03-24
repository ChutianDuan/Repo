from python_rag.infra.mysql import get_mysql_connection


def delete_chunks_by_doc_id(doc_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM doc_chunks WHERE doc_id=%s",
                (doc_id,),
            )
    finally:
        conn.close()


def bulk_insert_chunks(doc_id, chunks):
    if not chunks:
        return 0

    conn = get_mysql_connection()
    try:
        rows = []
        for idx, text in enumerate(chunks):
            tokens_est = len(text.split())
            rows.append((doc_id, idx, text, tokens_est))

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