from python_rag.infra.mysql import get_mysql_connection
from python_rag.utils.to_iso import _to_iso


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
                        float(item.get("score") or 0),
                        item.get("snippet") or (item.get("content") or "")[:300],
                    )
                )
            cursor.executemany(sql, data)
            return cursor.rowcount
    finally:
        conn.close()


def list_citations_by_message_ids(message_ids):
    if not message_ids:
        return {}

    placeholders = ",".join(["%s"] * len(message_ids))

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
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
                ORDER BY message_id ASC, score DESC, id ASC
                """,
                tuple(message_ids),
            )
            rows = cursor.fetchall()

            grouped = {}
            for row in rows:
                citation = {
                    "citation_id": row["id"],
                    "doc_id": row["doc_id"],
                    "chunk_id": row["chunk_id"],
                    "chunk_index": row["chunk_index"],
                    "score": float(row["score"]) if row["score"] is not None else 0.0,
                    "snippet": row.get("snippet") or "",
                    "created_at": _to_iso(row["created_at"]),
                }
                grouped.setdefault(row["message_id"], []).append(citation)

            return grouped
    finally:
        conn.close()
