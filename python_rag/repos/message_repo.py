from python_rag.infra.mysql import get_mysql_connection
from python_rag.utils.to_iso import _to_iso

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
            row["created_at"] = _to_iso(row["created_at"])
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
                row["created_at"] = _to_iso(row["created_at"]   )
                result.append(row)
            return result
    finally:
        conn.close()



def get_message_by_id(message_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, session_id, role, content, status, created_at
                FROM messages
                WHERE id=%s
                """,
                (message_id,),
            )
            row = cursor.fetchone()
            if row:
                row["message_id"] = row.pop("id")
                row["created_at"] = _to_iso(row["created_at"])
            return row
    finally:
        conn.close()


def update_message_status(message_id, status):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE messages
                SET status=%s
                    updated_at=CU
                WHERE id=%s
                """,
                (status, message_id),
            )
            conn.commit()
    finally:
        conn.close()