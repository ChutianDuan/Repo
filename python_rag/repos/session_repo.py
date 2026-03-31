from python_rag.infra.mysql import get_mysql_connection


def create_session(user_id, title):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (user_id, title)
                VALUES (%s, %s)
                """,
                (user_id, title),
            )
            session_id = cursor.lastrowid

            cursor.execute(
                """
                SELECT id, user_id, title, created_at
                FROM sessions
                WHERE id=%s
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            row["session_id"] = row.pop("id")
            row["created_at"] = row["created_at"].isoformat(sep="T", timespec="seconds")
            return row
    finally:
        conn.close()


def get_session_by_id(session_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, title, summary, created_at, updated_at
                FROM sessions
                WHERE id=%s
                """,
                (session_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()