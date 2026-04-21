from functools import lru_cache

from python_rag.infra.mysql import get_mysql_connection


@lru_cache(maxsize=128)
def has_column(table_name: str, column_name: str) -> bool:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
                LIMIT 1
                """,
                (table_name, column_name),
            )
            return cursor.fetchone() is not None
    finally:
        conn.close()
