import uuid

from celery.result import AsyncResult

from python_rag.core.error_codes import ERR_CELERY_ERROR, ERR_DB_ERROR,TaskState
from python_rag.core.errors import AppError
from python_rag.core.logger import logger

from python_rag.modules.tasks.repo import (
    create_task_record, get_task_by_celery_id,
    list_task_records,list_task_records_by_entity, update_task_record,)

from python_rag.modules.tasks.celery_app import celery_app
from python_rag.modules.tasks.worker_tasks.ping_task import ping_task
from python_rag.modules.tasks.worker_tasks.ingest_task import ingest_task


def submit_ping_job(seconds):
    try:
        async_result = ping_task.delay(seconds=seconds)

        db_task_id = create_task_record(
            celery_task_id=async_result.id,
            task_type="ping",
            entity_type="system",
            entity_id=0,
            state=TaskState.PENDING,
            progress=0,
            meta={"seconds": seconds},
        )

        return {
            "db_task_id": db_task_id,
            "task_id": async_result.id,
            "state": TaskState.PENDING,
            "status_url": "/internal/tasks/{0}".format(async_result.id),
        }
    except Exception as e:
        logger.exception("submit_ping_job failed")
        raise AppError(ERR_CELERY_ERROR, "submit_ping_job failed: {0}".format(e))


def submit_ingest_job(doc_id):
    try:
        celery_task_id = str(uuid.uuid4())

        db_task_id = create_task_record(
            celery_task_id=celery_task_id,
            task_type="ingest_document",
            entity_type="document",
            entity_id=doc_id,
            state=TaskState.PENDING,
            progress=0,
            meta={"doc_id": doc_id},
        )

        try:
            ingest_task.apply_async(
                kwargs={"doc_id": doc_id},
                task_id=celery_task_id,
            )
        except Exception as exc:
            update_task_record(
                celery_task_id=celery_task_id,
                state=TaskState.FAILURE,
                progress=100,
                meta={
                    "stage": "queue_failed",
                    "doc_id": doc_id,
                },
                error=str(exc),
            )
            raise

        return {
            "db_task_id": db_task_id,
            "task_id": celery_task_id,
            "state": TaskState.PENDING,
            "status_url": "/internal/tasks/{0}".format(celery_task_id),
        }
    except Exception as e:
        logger.exception("submit_ingest_job failed")
        raise AppError(ERR_CELERY_ERROR, "submit_ingest_job failed: {0}".format(e))


def get_task_status(task_id):
    try:
        row = get_task_by_celery_id(task_id)
        if row:
            return {
                "task_id": row["celery_task_id"],
                "state": row["state"],
                "progress": row["progress"],
                "meta": row["meta_json"],
                "error": row["error"],
            }

        async_result = AsyncResult(task_id, app=celery_app)
        meta = async_result.info if isinstance(async_result.info, dict) else None

        return {
            "task_id": task_id,
            "state": async_result.state,
            "progress": meta.get("progress", 0) if meta else 0,
            "meta": meta,
            "error": str(async_result.info) if async_result.failed() else None,
        }
    except AppError:
        raise
    except Exception as e:
        logger.exception("get_task_status failed")
        raise AppError(ERR_DB_ERROR, "get_task_status failed: {0}".format(e))
    

def list_tasks(limit=20, state=None):
    rows = list_task_records(limit=limit, state=state)
    return {
        "items": [
            {
                "db_task_id": row["id"],
                "task_id": row["celery_task_id"],
                "type": row["type"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "state": row["state"],
                "progress": row["progress"],
                "meta": row["meta_json"],
                "error": row["error"],
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]
    }


def list_tasks_by_entity(entity_type, entity_id, limit=20):
    rows = list_task_records_by_entity(
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return {
        "items": [
            {
                "db_task_id": row["id"],
                "task_id": row["celery_task_id"],
                "type": row["type"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "state": row["state"],
                "progress": row["progress"],
                "meta": row["meta_json"],
                "error": row["error"],
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]
    }
