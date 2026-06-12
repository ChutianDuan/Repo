import time
from typing import Any, Dict, List, Optional

from python_rag.app.core.error_codes import TaskState
from python_rag.app.core.logger import logger
from python_rag.app.core.config import CHAT_ENABLE_MOCK_FALLBACK

from python_rag.app.modules.messages.repo import (
    create_message,
    update_message_status,
)
from python_rag.app.modules.tasks.repo import update_task_record
from python_rag.app.modules.chat.repo import bulk_insert_citations
from python_rag.app.modules.chat.common import (
    NO_CONTEXT_ANSWER,
    build_citations_from_hits as _build_citations_from_hits,
    chunks_to_dicts as _chunks_to_dicts,
    generate_mock_answer,
    retrieve_hits as _retrieve_hits,
)
from python_rag.app.modules.chat.validation import validate_chat_user_message

from python_rag.app.modules.retrieval.context_assembler import assemble_context
from python_rag.app.modules.retrieval.prompt_builder import build_prompt, to_messages

from python_rag.app.modules.llm.service import LLMServiceError, generate_answer
from python_rag.app.modules.monitor.request_metrics import (
    build_usage_metrics,
    estimate_chat_cost_usd,
    estimate_text_tokens,
    is_timeout_error,
    record_request_metric,
    track_session_activity,
)


class ChatServiceError(Exception):
    pass


def _create_assistant_message(
    session_id: int,
    content: str,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> int:
    """
    优先尝试把 meta_json 一起写入。
    如果当前 create_message 还不支持 meta_json，则自动降级。
    """
    try:
        row = create_message(
            session_id=session_id,
            role="assistant",
            content=content,
            status="SUCCESS",
            meta_json=extra_meta or {},
        )
    except TypeError:
        row = create_message(
            session_id=session_id,
            role="assistant",
            content=content,
            status="SUCCESS",
        )

    if isinstance(row, dict):
        return row.get("message_id") or row.get("id")
    return row


def _save_citations(assistant_message_id: int, hits: List[Dict[str, Any]]) -> None:
    if not hits:
        return
    bulk_insert_citations(
        message_id=assistant_message_id,
        hits=hits,
    )


def _emit_progress(
    celery_task_id,
    state,
    progress,
    meta,
    progress_callback=None,
    error=None,
):
    if celery_task_id:
        update_task_record(
            celery_task_id=celery_task_id,
            state=state,
            progress=progress,
            meta=meta,
            error=error,
        )

    if progress_callback and state != TaskState.FAILURE:
        try:
            progress_callback(state=state, meta=dict(meta or {}, progress=progress))
        except Exception:
            logger.exception("chat progress_callback failed")


def run_chat_for_message(
    session_id: int,
    doc_id: Optional[int],
    user_message_id: int,
    top_k: Optional[int] = None,
    celery_task_id: Optional[str] = None,
    progress_callback=None,
    doc_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    top_k = top_k or 3
    doc_ids = doc_ids or []
    started_at = time.perf_counter()
    retrieval_ms = None
    faiss_ms = None
    lancedb_ms = None
    rerank_ms = None
    candidate_top_k = None
    final_top_k = top_k
    rerank_meta = {}
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None
    cost_usd = 0.0
    context_mode = None
    answer_source = None
    citation_count = 0
    resolved_doc_ids = []
    metric_doc_id = doc_id

    try:
        with track_session_activity(session_id=session_id, is_stream=False):
            _, _, question = validate_chat_user_message(
                session_id=session_id,
                user_message_id=user_message_id,
            )

            logger.info(
                "chat start session_id=%s doc_id=%s user_message_id=%s top_k=%s celery_task_id=%s",
                session_id,
                doc_id,
                user_message_id,
                top_k,
                celery_task_id,
            )

            _emit_progress(
                celery_task_id=celery_task_id,
                state=TaskState.STARTED,
                progress=10,
                meta={
                    "stage": "load_user_message",
                    "session_id": session_id,
                    "doc_id": doc_id,
                    "doc_ids": doc_ids,
                    "user_message_id": user_message_id,
                },
                progress_callback=progress_callback,
            )

            update_message_status(user_message_id, "PROCESSING")

            _emit_progress(
                celery_task_id=celery_task_id,
                state=TaskState.PROGRESS,
                progress=30,
                meta={
                    "stage": "retrieve",
                    "session_id": session_id,
                    "doc_id": doc_id,
                    "doc_ids": doc_ids,
                    "user_message_id": user_message_id,
                },
                progress_callback=progress_callback,
            )

            retrieval_result = _retrieve_hits(
                question=question,
                doc_id=doc_id,
                doc_ids=doc_ids,
                top_k=top_k,
            )
            raw_hits = retrieval_result.get("hits", [])
            resolved_doc_ids = retrieval_result.get("doc_ids") or ([] if doc_id is None else [doc_id])
            metric_doc_id = resolved_doc_ids[0] if len(resolved_doc_ids) == 1 else None
            retrieval_metrics = retrieval_result.get("metrics") or {}
            retrieval_ms = retrieval_metrics.get("retrieval_ms")
            faiss_ms = retrieval_metrics.get("faiss_ms")
            lancedb_ms = retrieval_metrics.get("lancedb_ms")
            rerank_ms = retrieval_metrics.get("rerank_ms")
            candidate_top_k = retrieval_metrics.get("candidate_top_k")
            final_top_k = retrieval_metrics.get("final_top_k") or top_k
            rerank_meta = retrieval_metrics.get("rerank") or {}

            chunks, context_mode = assemble_context(raw_hits, max_chunks=top_k)
            chunk_dicts = _chunks_to_dicts(chunks)
            citations = _build_citations_from_hits(raw_hits)
            citation_count = len(citations)

            logger.info(
                "chat retrieval done session_id=%s doc_id=%s user_message_id=%s raw_hit_count=%s chunk_count=%s context_mode=%s",
                session_id,
                doc_id,
                user_message_id,
                len(raw_hits),
                len(chunks),
                context_mode,
            )

            _emit_progress(
                celery_task_id=celery_task_id,
                state=TaskState.PROGRESS,
                progress=60,
                meta={
                    "stage": "generate_answer",
                    "session_id": session_id,
                    "doc_id": doc_id,
                    "doc_ids": resolved_doc_ids,
                    "user_message_id": user_message_id,
                    "retrieved_count": len(chunks),
                    "raw_hit_count": len(raw_hits),
                    "context_mode": context_mode,
                    "retrieval_ms": retrieval_ms,
                    "faiss_ms": faiss_ms,
                    "lancedb_ms": lancedb_ms,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": candidate_top_k,
                    "final_top_k": final_top_k,
                    "rerank": rerank_meta,
                },
                progress_callback=progress_callback,
            )

            prompt_result = build_prompt(
                question=question,
                chunks=chunks,
                mode=context_mode,
            )
            messages = to_messages(prompt_result)

            answer_text = ""
            answer_source = "unknown"
            llm_result = None

            if context_mode == "no_context":
                answer_text = NO_CONTEXT_ANSWER
                answer_source = "no_context"
            else:
                try:
                    llm_result = generate_answer(
                        question=question,
                        chunks=chunk_dicts,
                        messages=messages,
                    )
                    answer_text = llm_result["answer"]
                    answer_source = "llm"
                except LLMServiceError as e:
                    logger.exception(
                        "llm generate failed session_id=%s doc_id=%s user_message_id=%s",
                        session_id,
                        doc_id,
                        user_message_id,
                    )

                    if CHAT_ENABLE_MOCK_FALLBACK:
                        answer_text = generate_mock_answer(
                            question=question,
                            context_chunks=chunk_dicts,
                        )
                        answer_source = "mock_fallback"
                    else:
                        raise ChatServiceError(
                            "llm generate failed and mock fallback disabled: %s" % str(e)
                        )

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

            assistant_meta = {
                "answer_source": answer_source,
                "retrieved_count": len(chunks),
                "raw_hit_count": len(raw_hits),
                "citation_count": citation_count,
                "doc_id": doc_id,
                "doc_ids": resolved_doc_ids,
                "user_message_id": user_message_id,
                "context_mode": context_mode,
                "retrieval_ms": retrieval_ms,
                "faiss_ms": faiss_ms,
                    "lancedb_ms": lancedb_ms,
                "rerank_ms": rerank_ms,
                "candidate_top_k": candidate_top_k,
                "final_top_k": final_top_k,
                "rerank": rerank_meta,
                "e2e_latency_ms": e2e_latency_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
                "token_source": usage_metrics["token_source"],
            }

            if llm_result:
                assistant_meta["llm_model"] = llm_result.get("model")
                assistant_meta["llm_usage"] = llm_result.get("usage")
                assistant_meta["llm_finish_reason"] = llm_result.get("finish_reason")
                assistant_meta["llm_latency_ms"] = llm_result.get("latency_ms")

            _emit_progress(
                celery_task_id=celery_task_id,
                state=TaskState.PROGRESS,
                progress=80,
                meta={
                    "stage": "save_assistant_message",
                    "session_id": session_id,
                    "doc_id": doc_id,
                    "doc_ids": resolved_doc_ids,
                    "user_message_id": user_message_id,
                    "answer_source": answer_source,
                    "context_mode": context_mode,
                    "retrieval_ms": retrieval_ms,
                    "faiss_ms": faiss_ms,
                    "lancedb_ms": lancedb_ms,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": candidate_top_k,
                    "final_top_k": final_top_k,
                    "e2e_latency_ms": e2e_latency_ms,
                },
                progress_callback=progress_callback,
            )

            assistant_message_id = _create_assistant_message(
                session_id=session_id,
                content=answer_text,
                extra_meta=assistant_meta,
            )

            _save_citations(
                assistant_message_id=assistant_message_id,
                hits=raw_hits,
            )

            update_message_status(user_message_id, "SUCCESS")

            result = {
                "stage": "finished",
                "session_id": session_id,
                "doc_id": doc_id,
                "doc_ids": resolved_doc_ids,
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message_id,
                "retrieved_count": len(chunks),
                "raw_hit_count": len(raw_hits),
                "citation_count": citation_count,
                "answer_source": answer_source,
                "context_mode": context_mode,
                "retrieval_ms": retrieval_ms,
                "faiss_ms": faiss_ms,
                    "lancedb_ms": lancedb_ms,
                "rerank_ms": rerank_ms,
                "candidate_top_k": candidate_top_k,
                "final_top_k": final_top_k,
                "e2e_latency_ms": e2e_latency_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
                "no_context": context_mode == "no_context",
            }

            logger.info(
                "chat finished session_id=%s doc_id=%s user_message_id=%s assistant_message_id=%s "
                "retrieved_count=%s raw_hit_count=%s citation_count=%s answer_source=%s context_mode=%s",
                session_id,
                doc_id,
                user_message_id,
                assistant_message_id,
                len(chunks),
                len(raw_hits),
                citation_count,
                answer_source,
                context_mode,
            )

            record_request_metric(
                request_type="chat_async",
                status="success",
                channel="celery",
                session_id=session_id,
                doc_id=metric_doc_id,
                user_message_id=user_message_id,
                celery_task_id=celery_task_id,
                top_k=top_k,
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
                    "assistant_message_id": assistant_message_id,
                    "doc_ids": resolved_doc_ids,
                    "total_tokens": total_tokens,
                    "llm_latency_ms": llm_result.get("latency_ms") if llm_result else None,
                    "faiss_ms": faiss_ms,
                    "lancedb_ms": lancedb_ms,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": candidate_top_k,
                    "final_top_k": final_top_k,
                    "rerank": rerank_meta,
                    "token_source": usage_metrics["token_source"],
                },
            )

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
        e2e_latency_ms = int((time.perf_counter() - started_at) * 1000)

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
                    "doc_ids": resolved_doc_ids,
                    "user_message_id": user_message_id,
                    "error": str(e),
                },
                error=str(e),
                progress_callback=progress_callback,
            )
        except Exception:
            logger.exception("update_task_record FAILURE failed")

        record_request_metric(
            request_type="chat_async",
            status="error",
            channel="celery",
            session_id=session_id,
            doc_id=metric_doc_id,
            user_message_id=user_message_id,
            celery_task_id=celery_task_id,
            top_k=top_k,
            e2e_latency_ms=e2e_latency_ms,
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
                "doc_ids": resolved_doc_ids,
                "rerank_ms": rerank_ms,
                "faiss_ms": faiss_ms,
                    "lancedb_ms": lancedb_ms,
                "candidate_top_k": candidate_top_k,
                "final_top_k": final_top_k,
                "rerank": rerank_meta,
            },
        )

        raise
