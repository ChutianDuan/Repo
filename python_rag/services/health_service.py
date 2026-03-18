from ..cache import get_redis_client
from ..db import get_mysql_connection
from ..exceptions import AppException
from ..constants import DB_ERROR, REDIS_ERROR
from ..logger import logger


def check_mysql():
    try:
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 AS ok")
                result = cursor.fetchone()
                return result["ok"] == 1
        finally:
            conn.close()
    except Exception as e:
        logger.exception("MySQL health check failed")
        raise AppException(DB_ERROR, f"MySQL check failed: {e}")


def check_redis():
    try:
        client = get_redis_client()
        ok = client.ping()
        client.set("health:last_status", "ok")
        return ok
    except Exception as e:
        logger.exception("Redis health check failed")
        raise AppException(REDIS_ERROR, f"Redis check failed: {e}")


def get_health_status():
    mysql_status = False
    redis_status = False

    try:
        mysql_status = check_mysql()
    except AppException as e:
        mysql_status = e.message

    try:
        redis_status = check_redis()
    except AppException as e:
        redis_status = e.message

    return {
        "mysql": mysql_status,
        "redis": redis_status,
    }