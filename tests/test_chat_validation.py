import pytest

from python_rag.app.core.error_codes import (
    ERR_INVALID_REQUEST,
    ERR_MESSAGE_NOT_FOUND,
    ERR_SESSION_NOT_FOUND,
)
from python_rag.app.core.errors import AppError
from python_rag.app.modules.chat import validation


def test_validate_chat_user_message_accepts_user_message(monkeypatch):
    monkeypatch.setattr(
        validation,
        "get_session_by_id",
        lambda session_id: {"session_id": session_id},
    )
    monkeypatch.setattr(
        validation,
        "get_message_by_id",
        lambda message_id: {
            "message_id": message_id,
            "session_id": 10,
            "role": "user",
            "content": "  hello  ",
        },
    )

    session, message, question = validation.validate_chat_user_message(
        session_id=10,
        user_message_id=20,
    )

    assert session["session_id"] == 10
    assert message["message_id"] == 20
    assert question == "hello"


def test_validate_chat_user_message_rejects_missing_session(monkeypatch):
    monkeypatch.setattr(validation, "get_session_by_id", lambda session_id: None)
    monkeypatch.setattr(validation, "get_message_by_id", lambda message_id: None)

    with pytest.raises(AppError) as exc:
        validation.validate_chat_user_message(session_id=10, user_message_id=20)

    assert exc.value.code == ERR_SESSION_NOT_FOUND
    assert exc.value.http_status == 404


def test_validate_chat_user_message_rejects_missing_message(monkeypatch):
    monkeypatch.setattr(
        validation,
        "get_session_by_id",
        lambda session_id: {"session_id": session_id},
    )
    monkeypatch.setattr(validation, "get_message_by_id", lambda message_id: None)

    with pytest.raises(AppError) as exc:
        validation.validate_chat_user_message(session_id=10, user_message_id=20)

    assert exc.value.code == ERR_MESSAGE_NOT_FOUND
    assert exc.value.http_status == 404


def test_validate_chat_user_message_rejects_non_user_role(monkeypatch):
    monkeypatch.setattr(
        validation,
        "get_session_by_id",
        lambda session_id: {"session_id": session_id},
    )
    monkeypatch.setattr(
        validation,
        "get_message_by_id",
        lambda message_id: {
            "message_id": message_id,
            "session_id": 10,
            "role": "assistant",
            "content": "answer",
        },
    )

    with pytest.raises(AppError) as exc:
        validation.validate_chat_user_message(session_id=10, user_message_id=20)

    assert exc.value.code == ERR_INVALID_REQUEST
    assert "role" in exc.value.message


def test_validate_chat_user_message_rejects_cross_session_message(monkeypatch):
    monkeypatch.setattr(
        validation,
        "get_session_by_id",
        lambda session_id: {"session_id": session_id},
    )
    monkeypatch.setattr(
        validation,
        "get_message_by_id",
        lambda message_id: {
            "message_id": message_id,
            "session_id": 99,
            "role": "user",
            "content": "hello",
        },
    )

    with pytest.raises(AppError) as exc:
        validation.validate_chat_user_message(session_id=10, user_message_id=20)

    assert exc.value.code == ERR_INVALID_REQUEST
    assert "belong" in exc.value.message
