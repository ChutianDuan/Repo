from python_rag.infra.mysql import get_mysql_connection


def create_message(session_id, role, content, status="SUCCESS"):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages (session_id, role, content, status)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, role, content, status),
            )
            message_id = cursor.lastrowid

            cursor.execute(
                """
                SELECT id, session_id, role, content, status, created_at
                FROM messages
                WHERE id=%s
                """,
                (message_id,),
            )
            row = cursor.fetchone()
            row["message_id"] = row.pop("id")
            row["created_at"] = row["created_at"].isoformat(sep="T", timespec="seconds")
            return row
    finally:
        conn.close()


def list_messages_by_session_id(session_id, limit=100):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, session_id, role, content, status, created_at
                FROM messages
                WHERE session_id=%s
                ORDER BY id ASC
                LIMIT %s
                """,
                (session_id, limit),
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                row["message_id"] = row.pop("id")
                row["created_at"] = row["created_at"].isoformat(sep="T", timespec="seconds")
                result.append(row)
            return result
    finally:
        conn.close()