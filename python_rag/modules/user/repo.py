from python_rag.infra.mysql import get_mysql_connection

def create_user(name: str):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO user_account (username) VALUES (%s)", (name,))
            user_id = cursor.lastrowid
            cursor.execute(
                "SELECT id, username, created_at FROM user_account WHERE id = %s",
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
                "SELECT id, username, created_at FROM user_account ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    return rows
