from python_rag.core.error_codes import ERR_INVALID_REQUEST
from python_rag.core.errors import AppError
from python_rag.modules.chat import streaming_service


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def test_stream_chat_emits_error_event_when_validation_fails(monkeypatch):
    statuses = []
    metrics = []

    def reject_message(session_id, user_message_id):
        raise AppError(ERR_INVALID_REQUEST, "message role must be user")

    monkeypatch.setattr(
        streaming_service,
        "track_session_activity",
        lambda **kwargs: _NullContext(),
    )
    monkeypatch.setattr(
        streaming_service,
        "validate_chat_user_message",
        reject_message,
    )
    monkeypatch.setattr(
        streaming_service,
        "update_message_status",
        lambda message_id, status: statuses.append((message_id, status)),
    )
    monkeypatch.setattr(
        streaming_service,
        "record_request_metric",
        lambda **kwargs: metrics.append(kwargs),
    )

    events = list(
        streaming_service.stream_chat_for_message(
            session_id=10,
            doc_id=None,
            user_message_id=20,
            top_k=3,
        )
    )

    assert len(events) == 1
    assert events[0].startswith("data: ")
    assert '"type": "error"' in events[0]
    assert "message role must be user" in events[0]
    assert statuses == [(20, "FAILURE")]
    assert metrics[0]["request_type"] == "chat_stream"
    assert metrics[0]["status"] == "error"
