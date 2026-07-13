import logging
import time
from dataclasses import dataclass, field
from threading import Condition, RLock, Thread
from typing import Generator, List, Optional, Tuple

from python_rag.app.core.error_codes import ERR_STREAM_ABORTED
from python_rag.app.modules.chat.stream_event_builder import build_error_event
from python_rag.app.modules.chat.streaming_service import stream_chat_for_message
from python_rag.app.shared.sse import (
    add_sse_event_id,
    build_sse_comment,
    is_terminal_sse,
    parse_last_event_id,
    resume_requested,
)


logger = logging.getLogger(__name__)

STREAM_RESUME_TTL_SECONDS = 15 * 60
STREAM_HEARTBEAT_SECONDS = 15.0
MAX_COMPLETED_STREAMS = 128

StreamKey = Tuple[int, int, Optional[int], Tuple[int, ...], int]


@dataclass
class _ChatStreamState:
    key: StreamKey
    created_at: float
    updated_at: float
    next_event_id: int = 1
    events: List[Tuple[int, str]] = field(default_factory=list)
    completed_at: Optional[float] = None
    condition: Condition = field(default_factory=Condition)


_STREAMS: dict[StreamKey, _ChatStreamState] = {}
_STREAMS_LOCK = RLock()


def _stream_key(
    session_id: int,
    user_message_id: int,
    doc_id: Optional[int],
    doc_ids: List[int],
    top_k: int,
) -> StreamKey:
    return (session_id, user_message_id, doc_id, tuple(doc_ids), top_k)


def _append_event(state: _ChatStreamState, raw_event: str) -> None:
    with state.condition:
        event_id = state.next_event_id
        numbered_event = add_sse_event_id(raw_event, event_id)
        state.next_event_id += 1
        state.events.append((event_id, numbered_event))
        state.updated_at = time.monotonic()
        if is_terminal_sse(numbered_event):
            state.completed_at = state.updated_at
        state.condition.notify_all()


def _finish_state(state: _ChatStreamState) -> None:
    with state.condition:
        if state.completed_at is None:
            state.completed_at = time.monotonic()
        state.condition.notify_all()


def _run_stream(
    state: _ChatStreamState,
    session_id: int,
    doc_id: Optional[int],
    user_message_id: int,
    top_k: int,
    doc_ids: List[int],
) -> None:
    terminal_emitted = False
    try:
        for raw_event in stream_chat_for_message(
            session_id=session_id,
            doc_id=doc_id,
            doc_ids=doc_ids,
            user_message_id=user_message_id,
            top_k=top_k,
        ):
            _append_event(state, raw_event)
            if is_terminal_sse(raw_event):
                terminal_emitted = True
                break
        if not terminal_emitted:
            _append_event(
                state,
                build_error_event("stream ended without a terminal event"),
            )
    except Exception as exc:
        logger.exception(
            "chat stream worker failed session_id=%s user_message_id=%s",
            session_id,
            user_message_id,
        )
        _append_event(state, build_error_event(str(exc)))
    finally:
        _finish_state(state)


def _cleanup_stream_registry(now: float) -> None:
    expired = [
        key
        for key, state in _STREAMS.items()
        if state.completed_at is not None
        and now - state.completed_at > STREAM_RESUME_TTL_SECONDS
    ]
    for key in expired:
        _STREAMS.pop(key, None)

    completed = [state for state in _STREAMS.values() if state.completed_at is not None]
    completed.sort(key=lambda item: item.completed_at or item.updated_at)
    for state in completed[:-MAX_COMPLETED_STREAMS]:
        _STREAMS.pop(state.key, None)


def _expired_resume_state(key: StreamKey, last_event_id: int) -> _ChatStreamState:
    now = time.monotonic()
    state = _ChatStreamState(
        key=key,
        created_at=now,
        updated_at=now,
        next_event_id=last_event_id + 1,
    )
    error = build_error_event("stream resume state expired", ERR_STREAM_ABORTED)
    _append_event(state, error)
    return state


def _get_or_start_stream_state(
    session_id: int,
    doc_id: Optional[int],
    user_message_id: int,
    top_k: int,
    doc_ids: List[int],
    last_event_id: Optional[str],
) -> _ChatStreamState:
    key = _stream_key(session_id, user_message_id, doc_id, doc_ids, top_k)
    now = time.monotonic()
    with _STREAMS_LOCK:
        _cleanup_stream_registry(now)
        existing = _STREAMS.get(key)
        if existing is not None:
            with existing.condition:
                is_active = existing.completed_at is None
            if is_active or resume_requested(last_event_id):
                return existing

        if resume_requested(last_event_id):
            state = _expired_resume_state(key, parse_last_event_id(last_event_id))
            _STREAMS[key] = state
            return state

        state = _ChatStreamState(key=key, created_at=now, updated_at=now)
        _STREAMS[key] = state
        worker = Thread(
            target=_run_stream,
            kwargs={
                "state": state,
                "session_id": session_id,
                "doc_id": doc_id,
                "doc_ids": doc_ids,
                "user_message_id": user_message_id,
                "top_k": top_k,
            },
            name="chat-stream-{0}".format(user_message_id),
            daemon=True,
        )
        worker.start()
        return state


def stream_resumable_chat(
    session_id: int,
    doc_id: Optional[int],
    user_message_id: int,
    top_k: int,
    doc_ids: Optional[List[int]] = None,
    last_event_id: Optional[str] = None,
) -> Generator[str, None, None]:
    normalized_doc_ids = list(doc_ids or [])
    state = _get_or_start_stream_state(
        session_id=session_id,
        doc_id=doc_id,
        doc_ids=normalized_doc_ids,
        user_message_id=user_message_id,
        top_k=top_k,
        last_event_id=last_event_id,
    )
    cursor = parse_last_event_id(last_event_id)

    while True:
        heartbeat = False
        with state.condition:
            while (
                not any(event_id > cursor for event_id, _ in state.events)
                and state.completed_at is None
            ):
                notified = state.condition.wait(timeout=STREAM_HEARTBEAT_SECONDS)
                if not notified:
                    heartbeat = True
                    break

            pending = [record for record in state.events if record[0] > cursor]
            completed = state.completed_at is not None

        if heartbeat and not pending:
            yield build_sse_comment()
            continue

        for event_id, raw_event in pending:
            cursor = event_id
            yield raw_event
            if is_terminal_sse(raw_event):
                return

        if completed:
            return


def _reset_chat_stream_registry_for_tests() -> None:
    with _STREAMS_LOCK:
        _STREAMS.clear()


__all__ = ["stream_resumable_chat"]
