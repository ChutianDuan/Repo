# python_rag/db.py
import pymysql
from .config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_DATABASE,
    MYSQL_USER,
    MYSQL_PASSWORD,
)


def get_mysql_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def execute_sql_file(sql_path):
    conn = get_mysql_connection()
    try:
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_text = f.read()

        statements = [x.strip() for x in sql_text.split(";") if x.strip()]
        with conn.cursor() as cursor:
            for stmt in statements:
                cursor.execute(stmt)
    finally:
        conn.close()