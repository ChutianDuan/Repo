from python_rag.infra.mysql import get_mysql_connection


def bulk_insert_citations(message_id, hits):
    if not hits:
        return 0

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO citations (
                    message_id, doc_id, chunk_id, chunk_index, score, snippet
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            data = []
            for item in hits:
                data.append(
                    (
                        message_id,
                        item["doc_id"],
                        item["chunk_id"],
                        item["chunk_index"],
                        float(item["score"]),
                        item.get("snippet", ""),
                    )
                )
            cursor.executemany(sql, data)
            return cursor.rowcount
    finally:
        conn.close()


def list_citations_by_message_ids(message_ids):
    if not message_ids:
        return {}

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(message_ids))
            cursor.execute(
                f"""
                SELECT
                    id,
                    message_id,
                    doc_id,
                    chunk_id,
                    chunk_index,
                    score,
                    snippet,
                    created_at
                FROM citations
                WHERE message_id IN ({placeholders})
                ORDER BY id ASC
                """,
                tuple(message_ids),
            )
            rows = cursor.fetchall()

            grouped = {}
            for row in rows:
                mid = row["message_id"]
                grouped.setdefault(mid, []).append(
                    {
                        "doc_id": row["doc_id"],
                        "chunk_id": row["chunk_id"],
                        "chunk_index": row["chunk_index"],
                        "score": float(row["score"]),
                        "snippet": row["snippet"] or "",
                    }
                )
            return grouped
    finally:
        conn.close()