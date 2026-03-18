from ..cache import get_redis_client
from ..constants import DB_ERROR, REDIS_ERROR
from ..exceptions import AppException
from ..logger import logger
from ..models import create_task_record,get_latest_task_records


def create_task(user_id: int, task_type: str, input_text: str):
    try:
        task_id = create_task_record(user_id, task_type, input_text)
    except Exception as e:
        logger.exception("Create task db operation failed")
        raise AppException(DB_ERROR, f"Create task failed: {e}")

    try:
        client = get_redis_client()
        client.set("task:last_created_id", task_id)
    except Exception as e:
        logger.exception("Create task redis cache failed")
        raise AppException(REDIS_ERROR, f"Task created but cache failed: {e}")

    return task_id

def get_latest_task_records(limit: int = 5):
    try:
        rows = get_latest_task_records(limit)
    except Exception as e:
        logger.exception("Get latest task records db operation failed")
        raise AppException(DB_ERROR, f"Query latest task records failed: {e}")

    try:
        client = get_redis_client()
        client.set("tasks:last_query_limit", str(limit))
    except Exception as e:
        logger.exception("Latest task records redis cache failed")
        raise AppException(REDIS_ERROR, f"Query succeeded but cache failed: {e}")

    return rows