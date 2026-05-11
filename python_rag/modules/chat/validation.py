from typing import Any, Dict, Tuple

from python_rag.core.error_codes import (
    ERR_INVALID_REQUEST,
    ERR_MESSAGE_NOT_FOUND,
    ERR_SESSION_NOT_FOUND,
)
from python_rag.core.errors import AppError
from python_rag.modules.messages.repo import get_message_by_id
from python_rag.modules.sessions.repo import get_session_by_id


def validate_chat_user_message(
    session_id: int,
    user_message_id: int,
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    session = get_session_by_id(session_id)
    if not session:
        raise AppError(ERR_SESSION_NOT_FOUND, "session not found", http_status=404)

    user_message = get_message_by_id(user_message_id)
    if not user_message:
        raise AppError(ERR_MESSAGE_NOT_FOUND, "user message not found", http_status=404)

    if user_message.get("session_id") != session_id:
        raise AppError(ERR_INVALID_REQUEST, "user message does not belong to session")

    if user_message.get("role") != "user":
        raise AppError(ERR_INVALID_REQUEST, "message role must be user")

    question = str(user_message.get("content") or "").strip()
    if not question:
        raise AppError(ERR_INVALID_REQUEST, "user message content is empty")

    return session, user_message, question
