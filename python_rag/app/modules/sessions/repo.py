from python_rag.app.infra.mysql import get_mysql_connection
from python_rag.app.infra.schema_support import has_column
from python_rag.app.shared.to_iso import _to_iso


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
            row["created_at"] = _to_iso(row["created_at"])
            return row
    finally:
        conn.close()


def get_session_by_id(session_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            fields = ["id", "user_id", "title", "summary", "created_at"]
            if has_column("sessions", "summary_message_id"):
                fields.append("summary_message_id")
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


def update_session_summary(session_id, summary, summary_message_id=None):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            fields = ["summary=%s"]
            params = [summary]
            if (
                summary_message_id is not None
                and has_column("sessions", "summary_message_id")
            ):
                fields.append("summary_message_id=%s")
                params.append(summary_message_id)
            if has_column("sessions", "updated_at"):
                fields.append("updated_at=CURRENT_TIMESTAMP")
            params.append(session_id)

            cursor.execute(
                """
                UPDATE sessions
                SET {fields}
                WHERE id=%s
                """.format(fields=", ".join(fields)),
                tuple(params),
            )
    finally:
        conn.close()
