import uuid

from python_rag.core.error_codes import (
    TaskState,
)
from python_rag.modules.chat.validation import validate_chat_user_message
from python_rag.modules.tasks.repo import create_task_record, update_task_record
from python_rag.modules.tasks.worker_tasks.chat_task import chat_task


def submit_chat_job(session_id, doc_id=None, user_message_id=None, top_k=3, doc_ids=None):
    validate_chat_user_message(
        session_id=session_id,
        user_message_id=user_message_id,
    )

    celery_task_id = str(uuid.uuid4())

    db_task_id = create_task_record(
        celery_task_id=celery_task_id,
        task_type="chat_generate",
        entity_type="session",
        entity_id=session_id,
        state=TaskState.PENDING,
        progress=0,
        meta={
            "stage": "queued",
            "session_id": session_id,
            "doc_id": doc_id,
            "doc_ids": doc_ids or [],
            "user_message_id": user_message_id,
        },
    )

    try:
        chat_task.apply_async(
            kwargs={
                "session_id": session_id,
                "doc_id": doc_id,
                "doc_ids": doc_ids or [],
                "user_message_id": user_message_id,
                "top_k": top_k,
            },
            task_id=celery_task_id,
        )
    except Exception as exc:
        update_task_record(
            celery_task_id=celery_task_id,
            state=TaskState.FAILURE,
            progress=100,
            meta={
                "stage": "queue_failed",
                "session_id": session_id,
                "doc_id": doc_id,
                "doc_ids": doc_ids or [],
                "user_message_id": user_message_id,
            },
            error=str(exc),
        )
        raise

    return {
        "db_task_id": db_task_id,
        "task_id": celery_task_id,
        "state": TaskState.PENDING,
        "status_url": f"/internal/tasks/{celery_task_id}",
    }
