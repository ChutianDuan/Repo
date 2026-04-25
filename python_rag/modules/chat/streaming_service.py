import logging
import time
from typing import Any, Dict, Generator, List, Optional

from python_rag.core.error_codes import ERR_INTERNAL_ERROR, ERR_SESSION_NOT_FOUND
from python_rag.core.errors import AppError

from python_rag.modules.messages.repo import (
    get_message_by_id,
    list_recent_messages_by_session_id,
    update_message_status,
)
from python_rag.modules.sessions.repo import get_session_by_id

from python_rag.modules.retrieval.service import search_in_document
from python_rag.modules.retrieval.context_assembler import assemble_context

from python_rag.modules.llm.service import LLMServiceError, stream_answer
from python_rag.modules.llm.mock_service import build_mock_answer

from python_rag.modules.chat.stream_event_builder import (
    build_delta_event,
    build_done_event,
    build_error_event,
)
from python_rag.modules.chat.conversation_assembler import ConversationAssembler
from python_rag.modules.chat.prompt_templates import SYSTEM_PROMPT

from python_rag.config import (
    STREAM_DELTA_CHARS,
    STREAM_MOCK_DELAY_MS,
    CHAT_TOP_K,
    CHAT_ENABLE_MOCK_FALLBACK,
)

from python_rag.modules.chat.stream_persistence import persist_stream_result
from python_rag.modules.monitor.request_metrics import (
    build_usage_metrics,
    estimate_chat_cost_usd,
    estimate_text_tokens,
    is_timeout_error,
    record_request_metric,
    track_session_activity,
)

logger = logging.getLogger(__name__)


class StreamingChatServiceError(Exception):
    pass


def _get_user_message(user_message_id: int) -> Dict[str, Any]:
    message = get_message_by_id(user_message_id)
    if not message:
        raise StreamingChatServiceError("user message not found")
    return message


def _get_session(session_id: int) -> Dict[str, Any]:
    session = get_session_by_id(session_id)
    if not session:
        raise AppError(ERR_SESSION_NOT_FOUND, "session not found", http_status=404)
    return session


def _safe_get_question_from_message(user_message: Dict[str, Any]) -> str:
    content = user_message.get("content")
    if not content:
        raise StreamingChatServiceError("user message content is empty")
    return str(content).strip()


def _retrieve_hits(question: str, doc_id: int, top_k: int) -> Dict[str, Any]:
    result = search_in_document(
        query=question,
        doc_id=doc_id,
        top_k=top_k,
        track_metric=False,
    )
    return result or {}


def _chunk_to_dict(chunk: Any) -> Dict[str, Any]:
    if isinstance(chunk, dict):
        return chunk
    if hasattr(chunk, "__dict__"):
        return dict(chunk.__dict__)
    return {"content": str(chunk)}


def _chunks_to_dicts(chunks: List[Any]) -> List[Dict[str, Any]]:
    return [_chunk_to_dict(chunk) for chunk in chunks]


def _generate_mock_answer(question: str, context_chunks: List[Dict[str, Any]]) -> str:
    return build_mock_answer(
        user_query=question,
        hits=context_chunks,
    )


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    text = text or ""
    if chunk_size <= 0:
        chunk_size = 20
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def _mock_stream_answer(answer_text: str) -> Generator[str, None, None]:
    chunk_size = STREAM_DELTA_CHARS
    sleep_ms = STREAM_MOCK_DELAY_MS

    pieces = _chunk_text(answer_text, chunk_size)
    for idx, piece in enumerate(pieces, 1):
        yield build_delta_event(piece, idx)
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)


def _build_prompt_preview(messages: List[Dict[str, str]], max_chars: int = 4000) -> str:
    lines = []
    for i, msg in enumerate(messages, start=1):
        role = msg.get("role", "")
        content = (msg.get("content") or "").replace("\n", "\\n")
        if len(content) > 300:
            content = content[:300] + "...(truncated)"
        lines.append(f"[{i}] role={role} content={content}")
    preview = "\n".join(lines)
    if len(preview) > max_chars:
        preview = preview[:max_chars] + "\n...(prompt preview truncated)"
    return preview


def _stream_fallback_answer(answer_text: str) -> Generator[str, None, None]:
    for piece in _chunk_text(answer_text, STREAM_DELTA_CHARS):
        if piece:
            yield piece


def stream_chat_for_message(
    session_id: int,
    doc_id: int,
    user_message_id: int,
    top_k: Optional[int] = None,
) -> Generator[str, None, None]:
    top_k = top_k or CHAT_TOP_K
    started_at = time.perf_counter()
    retrieval_ms = None
    rerank_ms = None
    candidate_top_k = None
    final_top_k = top_k
    rerank_meta = {}
    ttft_ms = None
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None
    cost_usd = 0.0
    context_mode = None
    answer_source = None
    citation_count = 0

    try:
        with track_session_activity(session_id=session_id, is_stream=True):
            _get_session(session_id)

            user_message = _get_user_message(user_message_id)
            if user_message.get("session_id") != session_id:
                raise AppError(ERR_INTERNAL_ERROR, "user message does not belong to session")

            update_message_status(user_message_id, "PROCESSING")
            question = _safe_get_question_from_message(user_message)

            retrieval_result = _retrieve_hits(
                question=question,
                doc_id=doc_id,
                top_k=top_k,
            )
            raw_hits = retrieval_result.get("hits", [])
            retrieval_metrics = retrieval_result.get("metrics") or {}
            retrieval_ms = retrieval_metrics.get("retrieval_ms")
            rerank_ms = retrieval_metrics.get("rerank_ms")
            candidate_top_k = retrieval_metrics.get("candidate_top_k")
            final_top_k = retrieval_metrics.get("final_top_k") or top_k
            rerank_meta = retrieval_metrics.get("rerank") or {}
            chunks, context_mode = assemble_context(raw_hits, max_chunks=top_k)
            chunk_dicts = _chunks_to_dicts(chunks)
            citation_count = len(raw_hits)

            history_messages = list_recent_messages_by_session_id(
                session_id=session_id,
                limit=10,
            )

            assembler = ConversationAssembler(max_rounds=3)
            messages = assembler.build_messages(
                system_prompt=SYSTEM_PROMPT,
                history_messages=history_messages,
                retrieved_chunks=chunk_dicts,
                current_question=question,
                current_user_message_id=user_message_id,
            )

            logger.info(
                "stream chat start session_id=%s doc_id=%s user_message_id=%s retrieved_count=%s mode=%s",
                session_id,
                doc_id,
                user_message_id,
                len(chunks),
                context_mode,
            )
            logger.info(
                "stream chat prompt preview session_id=%s user_message_id=%s\n%s",
                session_id,
                user_message_id,
                _build_prompt_preview(messages),
            )

            llm_result = None
            answer_parts: List[str] = []
            stream_index = 0

            if context_mode == "no_context":
                answer_source = "no_context"
                for delta_text in _stream_fallback_answer(
                    "根据当前检索内容无法确定该问题的答案，因为没有检索到可用文档片段。"
                ):
                    stream_index += 1
                    answer_parts.append(delta_text)
                    if ttft_ms is None:
                        ttft_ms = int((time.perf_counter() - started_at) * 1000)
                    yield build_delta_event(delta_text, stream_index)
                answer_text = "".join(answer_parts)
            else:
                try:
                    for llm_event in stream_answer(
                        question=question,
                        chunks=chunk_dicts,
                        messages=messages,
                    ):
                        if llm_event.get("type") == "delta":
                            delta_text = str(llm_event.get("delta") or "")
                            if not delta_text:
                                continue
                            stream_index += 1
                            answer_parts.append(delta_text)
                            if ttft_ms is None:
                                ttft_ms = int((time.perf_counter() - started_at) * 1000)
                            yield build_delta_event(delta_text, stream_index)
                            continue

                        if llm_event.get("type") == "done":
                            llm_result = {
                                "answer": llm_event.get("answer") or "".join(answer_parts),
                                "model": llm_event.get("model"),
                                "usage": llm_event.get("usage"),
                                "finish_reason": llm_event.get("finish_reason"),
                                "latency_ms": llm_event.get("latency_ms"),
                                "ttft_ms": llm_event.get("ttft_ms"),
                            }

                    if not llm_result:
                        raise LLMServiceError("llm stream finished without done event")
                    answer_text = str(llm_result["answer"])
                    answer_source = "llm"
                except LLMServiceError:
                    if CHAT_ENABLE_MOCK_FALLBACK and not answer_parts:
                        answer_source = "mock_fallback"
                        for delta_text in _stream_fallback_answer(
                            _generate_mock_answer(
                                question=question,
                                context_chunks=chunk_dicts,
                            )
                        ):
                            stream_index += 1
                            answer_parts.append(delta_text)
                            if ttft_ms is None:
                                ttft_ms = int((time.perf_counter() - started_at) * 1000)
                            yield build_delta_event(delta_text, stream_index)
                        answer_text = "".join(answer_parts)
                    else:
                        raise

            usage_metrics = build_usage_metrics(
                usage=llm_result.get("usage") if llm_result else None,
                messages=messages,
                answer_text=answer_text,
            )
            prompt_tokens = usage_metrics["prompt_tokens"]
            completion_tokens = usage_metrics["completion_tokens"]
            total_tokens = usage_metrics["total_tokens"]
            cost_usd = estimate_chat_cost_usd(
                prompt_tokens=prompt_tokens if answer_source == "llm" else 0,
                completion_tokens=completion_tokens if answer_source == "llm" else 0,
                query_tokens=estimate_text_tokens(question) if answer_source == "llm" else 0,
            )

            e2e_latency_ms = int((time.perf_counter() - started_at) * 1000)
            assistant_message = persist_stream_result(
                session_id=session_id,
                answer_text=answer_text,
                retrieval_hits=raw_hits,
                answer_source=answer_source,
                context_mode=context_mode,
                extra_meta={
                    "user_message_id": user_message_id,
                    "retrieval_ms": retrieval_ms,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": candidate_top_k,
                    "final_top_k": final_top_k,
                    "ttft_ms": ttft_ms,
                    "e2e_latency_ms": e2e_latency_ms,
                    "citation_count": citation_count,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_usd,
                    "token_source": usage_metrics["token_source"],
                    "llm_model": llm_result.get("model") if llm_result else None,
                    "llm_usage": llm_result.get("usage") if llm_result else None,
                    "llm_finish_reason": llm_result.get("finish_reason") if llm_result else None,
                    "llm_latency_ms": llm_result.get("latency_ms") if llm_result else None,
                    "llm_ttft_ms": llm_result.get("ttft_ms") if llm_result else None,
                    "rerank": rerank_meta,
                },
            )
            update_message_status(user_message_id, "SUCCESS")

            record_request_metric(
                request_type="chat_stream",
                status="success",
                channel="sse",
                session_id=session_id,
                doc_id=doc_id,
                user_message_id=user_message_id,
                top_k=top_k,
                ttft_ms=ttft_ms,
                e2e_latency_ms=e2e_latency_ms,
                retrieval_ms=retrieval_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                citation_count=citation_count,
                no_context=context_mode == "no_context",
                context_mode=context_mode,
                answer_source=answer_source,
                extra={
                    "assistant_message_id": assistant_message["message_id"],
                    "total_tokens": total_tokens,
                    "llm_latency_ms": llm_result.get("latency_ms") if llm_result else None,
                    "llm_ttft_ms": llm_result.get("ttft_ms") if llm_result else None,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": candidate_top_k,
                    "final_top_k": final_top_k,
                    "rerank": rerank_meta,
                    "token_source": usage_metrics["token_source"],
                },
            )

            yield build_done_event(
                {
                    "assistant_message_id": assistant_message["message_id"],
                    "answer_source": answer_source,
                    "context_mode": context_mode,
                    "retrieved_count": len(chunks),
                    "citation_count": citation_count,
                    "retrieval_ms": retrieval_ms,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": candidate_top_k,
                    "final_top_k": final_top_k,
                    "ttft_ms": ttft_ms,
                    "e2e_latency_ms": e2e_latency_ms,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_usd,
                    "no_context": context_mode == "no_context",
                }
            )

    except Exception as e:
        logger.exception(
            "stream chat failed session_id=%s doc_id=%s user_message_id=%s",
            session_id,
            doc_id,
            user_message_id,
        )
        try:
            update_message_status(user_message_id, "FAILURE")
        except Exception:
            logger.exception("stream update_message_status FAILURE failed")

        record_request_metric(
            request_type="chat_stream",
            status="error",
            channel="sse",
            session_id=session_id,
            doc_id=doc_id,
            user_message_id=user_message_id,
            top_k=top_k,
            ttft_ms=ttft_ms,
            e2e_latency_ms=int((time.perf_counter() - started_at) * 1000),
            retrieval_ms=retrieval_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            citation_count=citation_count,
            no_context=context_mode == "no_context" if context_mode else False,
            timed_out=is_timeout_error(e),
            context_mode=context_mode,
            answer_source=answer_source,
            error_message=str(e),
            extra={
                "total_tokens": total_tokens,
                "rerank_ms": rerank_ms,
                "candidate_top_k": candidate_top_k,
                "final_top_k": final_top_k,
                "rerank": rerank_meta,
            },
        )
        yield build_error_event(str(e))
