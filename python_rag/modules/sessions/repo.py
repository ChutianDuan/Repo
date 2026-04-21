
from python_rag.infra.mysql import get_mysql_connection
from python_rag.infra.schema_support import has_column
from python_rag.utils.to_iso import _to_iso

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
            row["created_at"] =  _to_iso(row["created_at"])
            return row
    finally:
        conn.close()


def get_session_by_id(session_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            fields = ["id", "user_id", "title", "summary", "created_at"]
            if has_column("sessions", "updated_at"):
                fields.append("updated_at")
            cursor.execute(
                """
                SELECT {fields}
                FROM sessions
                WHERE id=%s
                """.format(fields=", ".join(fields)),
                (session_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()
