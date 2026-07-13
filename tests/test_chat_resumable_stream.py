from threading import Event

from python_rag.app.modules.chat import resumable_stream
from python_rag.app.modules.chat.stream_event_builder import (
    build_delta_event,
    build_done_event,
)


def test_chat_stream_resumes_without_restarting_generation(monkeypatch):
    resumable_stream._reset_chat_stream_registry_for_tests()
    release = Event()
    calls = []

    def fake_stream_chat_for_message(**kwargs):
        calls.append(kwargs)
        yield build_delta_event("first", 1)
        assert release.wait(timeout=1)
        yield build_delta_event("second", 2)
        yield build_done_event({"assistant_message_id": 99})

    monkeypatch.setattr(
        resumable_stream,
        "stream_chat_for_message",
        fake_stream_chat_for_message,
    )

    first_stream = resumable_stream.stream_resumable_chat(
        session_id=1,
        doc_id=None,
        doc_ids=[],
        user_message_id=2,
        top_k=3,
    )
    first_event = next(first_stream)
    first_stream.close()
    release.set()

    resumed = list(
        resumable_stream.stream_resumable_chat(
            session_id=1,
            doc_id=None,
            doc_ids=[],
            user_message_id=2,
            top_k=3,
            last_event_id="1",
        )
    )

    try:
        assert first_event.startswith("id: 1\n")
        assert "id: 1\n" not in "".join(resumed)
        assert resumed[0].startswith("id: 2\n")
        assert resumed[1].startswith("id: 3\n")
        assert '"type": "done"' in resumed[1]
        assert len(calls) == 1
    finally:
        resumable_stream._reset_chat_stream_registry_for_tests()


def test_chat_stream_reports_expired_resume_state():
    resumable_stream._reset_chat_stream_registry_for_tests()
    try:
        events = list(
            resumable_stream.stream_resumable_chat(
                session_id=10,
                doc_id=None,
                doc_ids=[],
                user_message_id=20,
                top_k=3,
                last_event_id="7",
            )
        )
    finally:
        resumable_stream._reset_chat_stream_registry_for_tests()

    assert len(events) == 1
    assert events[0].startswith("id: 8\n")
    assert '"type": "error"' in events[0]
    assert "stream resume state expired" in events[0]
