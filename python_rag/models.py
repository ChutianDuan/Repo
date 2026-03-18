

from .db import get_mysql_connection

def create_user(name: str):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO demo_user (name) VALUES (%s)", (name,))
            user_id = cursor.lastrowid
            cursor.execute(
                "SELECT id, name, created_at FROM demo_user WHERE id = %s",
                (user_id,),
            )
            row = cursor.fetchone()
    finally:
        conn.close()
    return row

def get_latest_users(limit: int = 5):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, created_at FROM demo_user ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    return rows

def create_task_record(user_id: int, task_type: str, input_text: str):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_task (user_id, task_type, input_text)
                VALUES (%s, %s, %s)
                """,
                (user_id, task_type, input_text),
            )
            new_id = cursor.lastrowid

            cursor.execute(
                """
                SELECT id, user_id, task_type, input_text, status, created_at
                FROM chat_task
                WHERE id = %s
                """,
                (new_id,),
            )
            row = cursor.fetchone()
            return row
    finally:
        conn.close()
def get_latest_task_records(limit: int = 5):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, user_id, task_type, input_text, status, created_at FROM chat_task ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    return rows