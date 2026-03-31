from python_rag.domain.constants.error_code import NOT_FOUND_ERROR, INTERNAL_ERROR
from python_rag.domain.constants.task_state import TaskState
from python_rag.domain.exceptions import AppException

from python_rag.repos.session_repo import get_session_by_id
from python_rag.repos.message_repo import get_message_by_id
from python_rag.repos.task_repo import create_task_record
from python_rag.workers.tasks.chat_task import chat_task


def submit_chat_job(session_id, doc_id, user_message_id, top_k=3):
    session = get_session_by_id(session_id)
    if not session:
        raise AppException(NOT_FOUND_ERROR, "session not found")

    user_msg = get_message_by_id(user_message_id)
    if not user_msg:
        raise AppException(NOT_FOUND_ERROR, "user message not found")

    if user_msg["session_id"] != session_id:
        raise AppException(INTERNAL_ERROR, "user message does not belong to session")

    if user_msg["role"] != "user":
        raise AppException(INTERNAL_ERROR, "message role must be user")

    async_result = chat_task.delay(
        session_id=session_id,
        doc_id=doc_id,
        user_message_id=user_message_id,
        top_k=top_k,
    )

    db_task_id = create_task_record(
        celery_task_id=async_result.id,
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

    return {
        "db_task_id": db_task_id,
        "task_id": async_result.id,
        "state": TaskState.PENDING,
        "status_url": f"/internal/tasks/{async_result.id}",
    }