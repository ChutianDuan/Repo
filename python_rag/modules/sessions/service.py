from python_rag.core.error_codes import ERR_INVALID_REQUEST, ERR_SESSION_NOT_FOUND
from python_rag.core.errors import AppError, SessionNotFoundError
from python_rag.modules.sessions.repo import create_session, get_session_by_id
from python_rag.modules.messages.repo import (
    create_message,
    get_message_by_id,
    list_messages_by_session_id,
    update_message_status,
)
from python_rag.modules.chat.repo import list_citations_by_message_ids

ALLOWED_MESSAGE_STATUSES = {"PENDING", "PROCESSING", "SUCCESS", "FAILURE"}


def create_session_service(user_id, title):
    title = (title or "New Session").strip() or "New Session"
    return create_session(user_id=user_id, title=title)


def create_message_service(session_id, role, content, status="SUCCESS"):
    session = get_session_by_id(session_id)
    if not session:
        raise SessionNotFoundError(ERR_SESSION_NOT_FOUND, "session not found")

    role = (role or "").strip()
    if role not in ("user", "assistant", "system"):
        raise AppError(ERR_INVALID_REQUEST, "invalid role")

    content = (content or "").strip()
    if not content:
        raise AppError(ERR_INVALID_REQUEST, "content is empty")

    msg = create_message(
        session_id=session_id,
        role=role,
        content=content,
        status=status,
    )
    msg["citations"] = []
    msg["meta"] = msg.get("meta") or {}
    return msg


def list_messages_service(session_id, limit=100):
    session = get_session_by_id(session_id)
    if not session:
        raise SessionNotFoundError(ERR_SESSION_NOT_FOUND, "session not found")

    items = list_messages_by_session_id(session_id=session_id, limit=limit)
    message_ids = [item["message_id"] for item in items]
    citations_map = list_citations_by_message_ids(message_ids)
    result = []
    for item in items:
        item["citations"] = citations_map.get(item["message_id"], [])
        result.append(item)

    return {
        "session_id": session_id,
        "items": result,
    }


def update_session_message_status_service(session_id, message_id, status):
    session = get_session_by_id(session_id)
    if not session:
        raise SessionNotFoundError(ERR_SESSION_NOT_FOUND, "session not found")

    normalized_status = (status or "").strip().upper()
    if normalized_status not in ALLOWED_MESSAGE_STATUSES:
        raise AppError(ERR_INVALID_REQUEST, "invalid message status")

    message = get_message_by_id(message_id)
    if not message:
        raise AppError(ERR_INVALID_REQUEST, "message not found")

    if message["session_id"] != session_id:
        raise AppError(ERR_INVALID_REQUEST, "message does not belong to session")

    update_message_status(message_id, normalized_status)
    updated = get_message_by_id(message_id)
    updated["citations"] = list_citations_by_message_ids([message_id]).get(message_id, [])
    return updated
