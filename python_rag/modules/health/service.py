from python_rag.infra.redis_client import get_redis_client
from python_rag.infra.mysql import get_mysql_connection
from python_rag.core.errors import AppError
from python_rag.core.error_codes import ERR_DB_ERROR, ERR_REDIS_ERROR
from python_rag.core.logger import logger


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
    except Exception:
        logger.exception("MySQL health check failed")
        raise AppError(ERR_DB_ERROR, "MySQL check failed", http_status=500)


def check_redis():
    try:
        client = get_redis_client()
        ok = client.ping()
        client.set("health:last_status", "ok")
        return ok
    except Exception:
        logger.exception("Redis health check failed")
        raise AppError(ERR_REDIS_ERROR, "Redis check failed", http_status=500)


def get_health_status():
    result = {
        "mysql": {"ok": False, "code": None, "message": None},
        "redis": {"ok": False, "code": None, "message": None},
    }

    try:
        result["mysql"]["ok"] = check_mysql()
    except AppError as e:
        result["mysql"]["code"] = e.code
        result["mysql"]["message"] = e.message

    try:
        result["redis"]["ok"] = check_redis()
    except AppError as e:
        result["redis"]["code"] = e.code
        result["redis"]["message"] = e.message

    result["ok"] = result["mysql"]["ok"] and result["redis"]["ok"]
    return result