from fastapi import FastAPI, Query
from db import get_mysql_connection, init_table
from cache import get_redis_client

app = FastAPI(title="AI Project Minimal API")


@app.on_event("startup")
def startup_event():
    init_table()


@app.get("/health")
def health():
    mysql_ok = False
    redis_ok = False

    try:
        conn = get_mysql_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS ok")
            result = cursor.fetchone()
            mysql_ok = result["ok"] == 1
        conn.close()
    except Exception as e:
        mysql_ok = str(e)

    try:
        client = get_redis_client()
        redis_ok = client.ping()
        client.set("health:last_status", "ok")
    except Exception as e:
        redis_ok = str(e)

    return {
        "mysql": mysql_ok,
        "redis": redis_ok,
    }


@app.post("/users/create")
def create_user(name: str = Query(..., min_length=1, max_length=64)):
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

    client = get_redis_client()
    client.set("user:last_created_name", name)

    return {
        "message": "user created",
        "data": row,
    }


@app.get("/users/latest")
def latest_users(limit: int = 5):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, created_at FROM demo_user ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()

    client = get_redis_client()
    client.set("users:last_query_limit", str(limit))

    return {
        "count": len(rows),
        "data": rows,
    }