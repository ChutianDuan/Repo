import uuid

from python_rag.core.error_codes import (
    ERR_INVALID_REQUEST,
    ERR_MESSAGE_NOT_FOUND,
    ERR_SESSION_NOT_FOUND,
    TaskState,
)
from python_rag.core.errors import AppError

from python_rag.modules.sessions.repo import get_session_by_id
from python_rag.modules.messages.repo import get_message_by_id
from python_rag.modules.tasks.repo import create_task_record, update_task_record
from python_rag.modules.tasks.worker_tasks.chat_task import chat_task


def submit_chat_job(session_id, doc_id, user_message_id, top_k=3):
    session = get_session_by_id(session_id)
    if not session:
        raise AppError(ERR_SESSION_NOT_FOUND, "session not found", http_status=404)

    user_msg = get_message_by_id(user_message_id)
    if not user_msg:
        raise AppError(ERR_MESSAGE_NOT_FOUND, "user message not found", http_status=404)

    if user_msg["session_id"] != session_id:
        raise AppError(ERR_INVALID_REQUEST, "user message does not belong to session")

    if user_msg["role"] != "user":
        raise AppError(ERR_INVALID_REQUEST, "message role must be user")

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
            "user_message_id": user_message_id,
        },
    )

    try:
        chat_task.apply_async(
            kwargs={
                "session_id": session_id,
                "doc_id": doc_id,
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
