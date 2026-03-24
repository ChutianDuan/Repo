from python_rag.infra.redis_client import get_redis_client
from python_rag.domain.constants.error_code import DB_ERROR
from python_rag.domain.exceptions import AppException
from python_rag.domain.logger import logger
from python_rag.repos.user_repo import (
    create_user as model_create_user,
    get_latest_users as model_get_latest_users,
)


def create_user(name: str):
    try:
        row = model_create_user(name)
    except Exception as e:
        logger.exception("Create user db operation failed")
        raise AppException(DB_ERROR, f"Create user failed: {e}")

    try:
        client = get_redis_client()
        client.set("user:last_created_name", name)
    except Exception:
        logger.exception("Create user redis cache failed")

    return row


def get_latest_users(limit: int = 5):
    try:
        rows = model_get_latest_users(limit)
    except Exception as e:
        logger.exception("Get latest users db operation failed")
        raise AppException(DB_ERROR, f"Query latest users failed: {e}")

    try:
        client = get_redis_client()
        client.set("users:last_query_limit", str(limit))
    except Exception:
        logger.exception("Latest users redis cache failed")

    return rows