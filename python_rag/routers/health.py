from fastapi import APIRouter

from ..db import get_mysql_connection
from ..cache import get_redis_client
from ..schemas import HealthData, ApiResponse
from ..logger import logger


router = APIRouter(prefix="/health", tags=["health"])

@router.get("", response_model=ApiResponse)
def health_check():
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
        logger.error(f"MySQL health check failed: {e}")

    try:
        client = get_redis_client()
        redis_ok = client.ping()
        client.set("health:last_status", "ok")
    except Exception as e:
        redis_ok = str(e)
        logger.error(f"Redis health check failed: {e}")

    return ApiResponse(
        data=HealthData(mysql=mysql_ok, redis=redis_ok),
    )

