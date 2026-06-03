import asyncio
import logging
import time
from contextlib import suppress
from typing import Any, AsyncGenerator, Dict, Optional

from python_rag.app.agent.orchestrator import AgentOrchestrator
from python_rag.app.modules.chat.stream_event_builder import (
    build_delta_event,
    build_done_event,
    build_error_event,
    build_sse_event,
)
from python_rag.app.modules.chat.repo import bulk_insert_citations
from python_rag.app.modules.messages.repo import create_message


logger = logging.getLogger(__name__)

AGENT_EVENT_TYPES = {"agent_step", "tool_call", "tool_result", "final"}


def _sse_for_event(event: Dict[str, Any]) -> str:
    event_type = str(event.get("type") or "")

    if event_type == "delta":
        return build_delta_event(
            delta=str(event.get("delta") or ""),
            index=int(event.get("index") or 0),
        )

    if event_type == "done":
        meta = event.get("meta")
        return build_done_event(meta if isinstance(meta, dict) else None)

    if event_type == "error":
        return build_error_event(str(event.get("message") or "agent stream error"))

    if event_type in AGENT_EVENT_TYPES:
        return build_sse_event(event, event=event_type)

    return build_sse_event(event)


async def stream_agent_chat(
    session_id: int,
    message: str,
    trace_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()
    started_at = time.perf_counter()

    async def emit(event: Dict[str, Any]) -> None:
        await queue.put(event)

    async def run_agent_task() -> None:
        try:
            question = str(message or "").strip()
            if not question:
                raise ValueError("message is required")

            user_message = create_message(
                session_id=session_id,
                role="user",
                content=question,
                status="SUCCESS",
                meta={"source": "agent_chat_stream"},
            )

            result = await AgentOrchestrator().run(
                question=question,
                trace_id=trace_id,
                session_id=session_id,
                user_message_id=user_message["message_id"],
                event_sink=emit,
            )

            assistant_message = create_message(
                session_id=session_id,
                role="assistant",
                content=result["answer"],
                status="SUCCESS",
                meta={
                    "source": "agent",
                    "answer_source": "agent",
                    "agent_run_id": result["run_id"],
                    "steps_used": result.get("steps_used"),
                    "citation_count": len(result.get("citations") or []),
                },
            )
            citations = result.get("citations") or []
            if citations:
                bulk_insert_citations(
                    message_id=assistant_message["message_id"],
                    hits=citations,
                )

            e2e_latency_ms = int((time.perf_counter() - started_at) * 1000)
            meta = {
                "run_id": result["run_id"],
                "agent_run_id": result["run_id"],
                "assistant_message_id": assistant_message["message_id"],
                "message_id": assistant_message["message_id"],
                "steps_used": result.get("steps_used"),
                "e2e_latency_ms": e2e_latency_ms,
                "answer_source": "agent",
                "citation_count": len(citations),
            }

            if result["answer"]:
                await emit({"type": "delta", "delta": result["answer"], "index": 1})

            await emit(
                {
                    "type": "final",
                    "run_id": result["run_id"],
                    "message_id": assistant_message["message_id"],
                    "answer": result["answer"],
                    "citations": citations,
                    "steps_used": result.get("steps_used"),
                    "e2e_latency_ms": e2e_latency_ms,
                }
            )
            await emit({"type": "done", "meta": meta})
        except Exception as exc:
            logger.exception(
                "agent stream failed session_id=%s trace_id=%s",
                session_id,
                trace_id,
            )
            await emit({"type": "error", "message": str(exc)})
        finally:
            await queue.put(sentinel)

    task = asyncio.create_task(run_agent_task())
    task_cancelled = False
    try:
        while True:
            event = await queue.get()
            if event is sentinel:
                break
            yield _sse_for_event(event)
    finally:
        if not task.done():
            task_cancelled = True
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    if not task_cancelled:
        await task


__all__ = ["stream_agent_chat"]
