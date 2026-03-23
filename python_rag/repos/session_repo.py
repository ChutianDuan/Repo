# python_rag/repos/session_repo.py
from python_rag.db import get_mysql_connection


def create_session(user_id, title="New Session"):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (user_id, title)
                VALUES (%s, %s)
                """,
                (user_id, title)
            )
            return cursor.lastrowid
    finally:
        conn.close()


def create_message(session_id, role, content, status="created"):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages (session_id, role, content, status)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, role, content, status)
            )
            return cursor.lastrowid
    finally:
        conn.close()