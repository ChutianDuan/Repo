from email import message
import re
from unittest import result

from python_rag.domain.constants.error_code import NOT_FOUND_ERROR
from python_rag.domain.exceptions import AppException
from python_rag.repos.session_repo import create_session, get_session_by_id
from python_rag.repos.message_repo import create_message, list_messages_by_session_id
from python_rag.repos.citation_repo import list_citations_by_message_ids


def create_session_service(user_id, title):
    title = (title or "New Session").strip() or "New Session"
    return create_session(user_id=user_id, title=title)


def create_message_service(session_id, role, content, status="SUCCESS"):
    session = get_session_by_id(session_id)
    if not session:
        raise AppException(NOT_FOUND_ERROR, "session not found")

    role = (role or "").strip()
    if role not in ("user", "assistant", "system"):
        raise ValueError("invalid role")

    content = (content or "").strip()
    if not content:
        raise ValueError("content is empty")

    msg = create_message(
        session_id=session_id,
        role=role,
        content=content,
        status=status,
    )
    msg['citations'] = []
    return msg


def list_messages_service(session_id, limit=100):
    session = get_session_by_id(session_id)
    if not session:
        raise AppException(NOT_FOUND_ERROR, "session not found")

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