from python_rag.domain.constants.error_code import NOT_FOUND_ERROR, INTERNAL_ERROR
from python_rag.domain.constants.task_state import TaskState
from python_rag.domain.exceptions import AppException
from python_rag.domain.logger import logger

from python_rag.repos.session_repo import get_session_by_id
from python_rag.repos.message_repo import (
    get_message_by_id,
    create_message,
    update_message_status,
)
from python_rag.repos.task_repo import update_task_record
from python_rag.services.retrieval_service import search_in_document
from python_rag.services.mock_answer_service import build_mock_answer
from python_rag.repos.citation_repo import bulk_insert_citations


def _emit_progress(celery_task_id, state, progress, meta, progress_callback=None, error=None):
    update_task_record(
        celery_task_id=celery_task_id,
        state=state,
        progress=progress,
        meta=meta,
        error=error,
    )

    if progress_callback:
        try:
            progress_callback(state=state, meta=dict(meta or {}, progress=progress))
        except Exception:
            logger.exception("chat progress_callback failed")


def run_chat_for_message(
    session_id,
    doc_id,
    user_message_id,
    top_k,
    celery_task_id,
    progress_callback=None,
):
    try:
        session = get_session_by_id(session_id)
        if not session:
            raise AppException(NOT_FOUND_ERROR, "session not found")

        user_msg = get_message_by_id(user_message_id)
        if not user_msg:
            raise AppException(NOT_FOUND_ERROR, "user message not found")

        if user_msg["session_id"] != session_id:
            raise AppException(INTERNAL_ERROR, "user message does not belong to session")

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.STARTED,
            progress=10,
            meta={
                "stage": "chat_started",
                "session_id": session_id,
                "doc_id": doc_id,
                "user_message_id": user_message_id,
            },
            progress_callback=progress_callback,
        )

        update_message_status(user_message_id, "PROCESSING")

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=35,
            meta={
                "stage": "retrieving_context",
                "session_id": session_id,
                "doc_id": doc_id,
                "user_message_id": user_message_id,
            },
            progress_callback=progress_callback,
        )

        retrieval_result = search_in_document(
            doc_id=doc_id,
            query=user_msg["content"],
            top_k=top_k,
        )

        hits = retrieval_result["hits"]

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=70,
            meta={
                "stage": "building_mock_answer",
                "session_id": session_id,
                "doc_id": doc_id,
                "user_message_id": user_message_id,
                "hit_count": len(hits),
            },
            progress_callback=progress_callback,
        )

        answer = build_mock_answer(
            user_query=user_msg["content"],
            hits=hits,
        )

        assistant_msg = create_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            status="SUCCESS",
        )

        bulk_insert_citations(
            message_id=assistant_msg["message_id"],
            hits=hits,
        )

        update_message_status(user_message_id, "SUCCESS")

        result = {
            "stage": "finished",
            "session_id": session_id,
            "doc_id": doc_id,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_msg["message_id"],
            "hit_count": len(hits),
        }

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.SUCCESS,
            progress=100,
            meta=result,
            progress_callback=progress_callback,
        )

        return result

    except Exception as e:
        logger.exception("run_chat_for_message failed")

        try:
            update_message_status(user_message_id, "FAILURE")
        except Exception:
            logger.exception("update_message_status FAILURE failed")

        try:
            _emit_progress(
                celery_task_id=celery_task_id,
                state=TaskState.FAILURE,
                progress=100,
                meta={
                    "stage": "failed",
                    "session_id": session_id,
                    "doc_id": doc_id,
                    "user_message_id": user_message_id,
                    "error": str(e),
                },
                error=str(e),
                progress_callback=progress_callback,
            )
        except Exception:
            logger.exception("update_task_record FAILURE failed")

        raise