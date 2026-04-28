import json
import math
import threading
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from python_rag.config import (
    EMBEDDING_COST_PER_1K_TOKENS,
    LLM_COMPLETION_COST_PER_1K_TOKENS,
    LLM_PROMPT_COST_PER_1K_TOKENS,
    MONITOR_METRICS_MAX_ROWS,
    MONITOR_METRICS_WINDOW_SECONDS,
)
from python_rag.core.logger import logger
from python_rag.infra.mysql import get_mysql_connection


_runtime_lock = threading.Lock()
_active_session_refs: Counter = Counter()
_active_sse_connections = 0
_metrics_table_enabled = True


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def estimate_text_tokens(text: str) -> int:
    normalized = (text or "").strip()
    if not normalized:
        return 0

    word_count = len(normalized.split())
    if word_count > 1:
        return word_count
    return len(normalized)


def estimate_messages_tokens(messages: Optional[List[Dict[str, str]]]) -> int:
    total = 0
    for message in messages or []:
        total += estimate_text_tokens(message.get("role") or "")
        total += estimate_text_tokens(message.get("content") or "")
        total += 4
    return total


def build_usage_metrics(
    usage: Optional[Dict[str, Any]],
    messages: Optional[List[Dict[str, str]]] = None,
    answer_text: str = "",
) -> Dict[str, Any]:
    usage = usage or {}

    prompt_tokens = _safe_int(usage.get("prompt_tokens"))
    if prompt_tokens is None:
        prompt_tokens = _safe_int(usage.get("input_tokens"))

    completion_tokens = _safe_int(usage.get("completion_tokens"))
    if completion_tokens is None:
        completion_tokens = _safe_int(usage.get("output_tokens"))

    token_source = "provider"
    if prompt_tokens is None:
        prompt_tokens = estimate_messages_tokens(messages)
        token_source = "estimated"

    if completion_tokens is None:
        completion_tokens = estimate_text_tokens(answer_text)
        token_source = "estimated"

    total_tokens = _safe_int(usage.get("total_tokens"))
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "token_source": token_source,
    }


def estimate_chat_cost_usd(
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    query_tokens: int = 0,
) -> float:
    prompt_cost = (prompt_tokens or 0) * LLM_PROMPT_COST_PER_1K_TOKENS / 1000.0
    completion_cost = (completion_tokens or 0) * LLM_COMPLETION_COST_PER_1K_TOKENS / 1000.0
    query_cost = query_tokens * EMBEDDING_COST_PER_1K_TOKENS / 1000.0
    return round(prompt_cost + completion_cost + query_cost, 8)


def estimate_embedding_cost_usd(embedding_tokens: Optional[int]) -> float:
    return round((embedding_tokens or 0) * EMBEDDING_COST_PER_1K_TOKENS / 1000.0, 8)


def is_timeout_error(error: Any) -> bool:
    message = str(error or "").lower()
    return "timeout" in message or "timed out" in message


def _disable_metrics_table(exc: Exception) -> None:
    global _metrics_table_enabled
    if _metrics_table_enabled:
        logger.warning("request_metrics disabled because persistence failed: %s", exc)
    _metrics_table_enabled = False


def _should_disable_metrics_table(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "request_metrics" in message
        and ("doesn't exist" in message or "unknown table" in message or "1146" in message)
    )


@contextmanager
def track_session_activity(session_id: Optional[int], is_stream: bool = False):
    global _active_sse_connections

    if session_id:
        with _runtime_lock:
            _active_session_refs[session_id] += 1
            if is_stream:
                _active_sse_connections += 1

    try:
        yield
    finally:
        if session_id:
            with _runtime_lock:
                _active_session_refs[session_id] -= 1
                if _active_session_refs[session_id] <= 0:
                    _active_session_refs.pop(session_id, None)
                if is_stream and _active_sse_connections > 0:
                    _active_sse_connections -= 1


def get_runtime_counters() -> Dict[str, int]:
    with _runtime_lock:
        return {
            "concurrent_sessions": len(_active_session_refs),
            "active_sse_connections": _active_sse_connections,
        }


def record_request_metric(
    request_type: str,
    status: str,
    channel: str = "internal",
    session_id: Optional[int] = None,
    doc_id: Optional[int] = None,
    user_message_id: Optional[int] = None,
    celery_task_id: Optional[str] = None,
    top_k: Optional[int] = None,
    ttft_ms: Optional[int] = None,
    e2e_latency_ms: Optional[int] = None,
    ready_latency_ms: Optional[int] = None,
    retrieval_ms: Optional[int] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    embedding_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    citation_count: Optional[int] = None,
    no_context: bool = False,
    timed_out: bool = False,
    context_mode: Optional[str] = None,
    answer_source: Optional[str] = None,
    error_message: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    if not _metrics_table_enabled:
        return

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO request_metrics (
                    request_type,
                    channel,
                    status,
                    session_id,
                    doc_id,
                    user_message_id,
                    celery_task_id,
                    top_k,
                    ttft_ms,
                    e2e_latency_ms,
                    ready_latency_ms,
                    retrieval_ms,
                    prompt_tokens,
                    completion_tokens,
                    embedding_tokens,
                    cost_usd,
                    citation_count,
                    no_context,
                    timed_out,
                    context_mode,
                    answer_source,
                    error_message,
                    extra_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    request_type,
                    channel,
                    status,
                    session_id,
                    doc_id,
                    user_message_id,
                    celery_task_id,
                    top_k,
                    ttft_ms,
                    e2e_latency_ms,
                    ready_latency_ms,
                    retrieval_ms,
                    prompt_tokens,
                    completion_tokens,
                    embedding_tokens,
                    cost_usd,
                    citation_count,
                    1 if no_context else 0,
                    1 if timed_out else 0,
                    context_mode,
                    answer_source,
                    error_message,
                    json.dumps(extra or {}, ensure_ascii=False),
                ),
            )
    except Exception as exc:
        if _should_disable_metrics_table(exc):
            _disable_metrics_table(exc)
        else:
            logger.exception("record_request_metric failed")
    finally:
        conn.close()


def _decode_extra_json(value: Any) -> Dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def list_request_metrics(
    window_seconds: int = MONITOR_METRICS_WINDOW_SECONDS,
    limit: int = MONITOR_METRICS_MAX_ROWS,
) -> List[Dict[str, Any]]:
    if not _metrics_table_enabled:
        return []

    since = datetime.now() - timedelta(seconds=max(1, window_seconds))
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    request_type,
                    channel,
                    status,
                    session_id,
                    doc_id,
                    user_message_id,
                    celery_task_id,
                    top_k,
                    ttft_ms,
                    e2e_latency_ms,
                    ready_latency_ms,
                    retrieval_ms,
                    prompt_tokens,
                    completion_tokens,
                    embedding_tokens,
                    cost_usd,
                    citation_count,
                    no_context,
                    timed_out,
                    context_mode,
                    answer_source,
                    error_message,
                    extra_json,
                    created_at
                FROM request_metrics
                WHERE created_at >= %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (since, max(1, limit)),
            )
            rows = cursor.fetchall()
    except Exception as exc:
        if _should_disable_metrics_table(exc):
            _disable_metrics_table(exc)
        else:
            logger.exception("list_request_metrics failed")
        return []
    finally:
        conn.close()

    for row in rows:
        row["extra"] = _decode_extra_json(row.pop("extra_json", None))
        row["no_context"] = bool(row.get("no_context"))
        row["timed_out"] = bool(row.get("timed_out"))
        row["cost_usd"] = _safe_float(row.get("cost_usd"))
    return rows


def _extract_numeric_values(rows: Iterable[Dict[str, Any]], field: str) -> List[float]:
    values = []
    for row in rows:
        value = _safe_float(row.get(field))
        if value is not None:
            values.append(value)
    return values


def _extract_extra_numeric_values(rows: Iterable[Dict[str, Any]], field: str) -> List[float]:
    values = []
    for row in rows:
        extra = row.get("extra") or {}
        if not isinstance(extra, dict):
            continue
        value = _safe_float(extra.get(field))
        if value is not None:
            values.append(value)
    return values


def _round_maybe(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def _percentile(values: List[float], percentile: int) -> Optional[float]:
    if not values:
        return None

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * percentile / 100.0
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]

    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _average(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _latency_summary(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {
            "last": None,
            "avg": None,
            "p50": None,
            "p95": None,
            "p99": None,
        }

    return {
        "last": _round_maybe(values[0], 1),
        "avg": _round_maybe(_average(values), 1),
        "p50": _round_maybe(_percentile(values, 50), 1),
        "p95": _round_maybe(_percentile(values, 95), 1),
        "p99": _round_maybe(_percentile(values, 99), 1),
    }


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def summarize_request_metrics(
    window_seconds: int = MONITOR_METRICS_WINDOW_SECONDS,
    limit: int = MONITOR_METRICS_MAX_ROWS,
) -> Dict[str, Any]:
    rows = list_request_metrics(window_seconds=window_seconds, limit=limit)
    runtime = get_runtime_counters()

    chat_rows = [row for row in rows if row.get("request_type") in ("chat_async", "chat_stream")]
    chat_success_rows = [row for row in chat_rows if row.get("status") == "success"]
    ingest_rows = [row for row in rows if row.get("request_type") == "ingest"]
    ingest_success_rows = [row for row in ingest_rows if row.get("status") == "success"]

    ttft_values = _extract_numeric_values(
        [row for row in chat_success_rows if row.get("request_type") == "chat_stream"],
        "ttft_ms",
    )
    e2e_values = _extract_numeric_values(chat_success_rows, "e2e_latency_ms")
    ingest_ready_values = _extract_numeric_values(ingest_success_rows, "ready_latency_ms")
    retrieval_values = _extract_numeric_values(
        [row for row in rows if row.get("retrieval_ms") is not None],
        "retrieval_ms",
    )
    document_parse_values = _extract_extra_numeric_values(ingest_success_rows, "text_extract_ms")
    chunk_count_values = _extract_extra_numeric_values(ingest_success_rows, "chunk_count")
    faiss_values = _extract_extra_numeric_values(rows, "faiss_ms")
    recall_values = _extract_extra_numeric_values(rows, "recall_at_k")
    mrr_values = _extract_extra_numeric_values(rows, "mrr")
    ndcg_values = _extract_extra_numeric_values(rows, "ndcg")

    prompt_values = _extract_numeric_values(
        [row for row in chat_success_rows if row.get("prompt_tokens") is not None],
        "prompt_tokens",
    )
    completion_values = _extract_numeric_values(
        [row for row in chat_success_rows if row.get("completion_tokens") is not None],
        "completion_tokens",
    )
    chat_cost_values = _extract_numeric_values(
        [row for row in chat_success_rows if row.get("cost_usd") is not None],
        "cost_usd",
    )
    ingest_cost_values = _extract_numeric_values(
        [row for row in ingest_success_rows if row.get("cost_usd") is not None],
        "cost_usd",
    )

    citation_values = _extract_numeric_values(
        [row for row in chat_success_rows if row.get("citation_count") is not None],
        "citation_count",
    )

    error_count = len([row for row in rows if row.get("status") != "success"])
    timeout_count = len([row for row in rows if row.get("timed_out")])
    no_context_count = len([row for row in chat_success_rows if row.get("no_context")])

    return {
        "experience": {
            "window_seconds": window_seconds,
            "chat_samples": len(chat_rows),
            "ingest_samples": len(ingest_rows),
            "ttft_ms": _latency_summary(ttft_values),
            "e2e_latency_ms": _latency_summary(e2e_values),
            "ingest_ready_ms": _latency_summary(ingest_ready_values),
        },
        "ingest": {
            "document_parse_ms": _latency_summary(document_parse_values),
            "chunk_count": _latency_summary(chunk_count_values),
        },
        "cost": {
            "prompt_tokens_avg": _round_maybe(_average(prompt_values), 1),
            "prompt_tokens_total": int(sum(prompt_values)) if prompt_values else 0,
            "completion_tokens_avg": _round_maybe(_average(completion_values), 1),
            "completion_tokens_total": int(sum(completion_values)) if completion_values else 0,
            "cost_per_request_usd": _round_maybe(_average(chat_cost_values), 8),
            "cost_per_document_usd": _round_maybe(_average(ingest_cost_values), 8),
            "chat_cost_total_usd": _round_maybe(sum(chat_cost_values), 8) if chat_cost_values else 0.0,
            "ingest_cost_total_usd": _round_maybe(sum(ingest_cost_values), 8) if ingest_cost_values else 0.0,
        },
        "throughput": {
            "qps": round(len(chat_rows) / max(1, window_seconds), 3),
            "concurrent_sessions": runtime["concurrent_sessions"],
            "worker_queue_depth": None,
            "active_sse_connections": runtime["active_sse_connections"],
        },
        "quality": {
            "error_rate": _ratio(error_count, len(rows)),
            "timeout_rate": _ratio(timeout_count, len(rows)),
            "retrieval_ms": _latency_summary(retrieval_values),
            "faiss_ms": _latency_summary(faiss_values),
            "citation_count_avg": _round_maybe(_average(citation_values), 2),
            "no_context_ratio": _ratio(no_context_count, len(chat_success_rows)),
            "retrieval_eval_samples": len(recall_values) or len(mrr_values) or len(ndcg_values),
            "recall_at_k_avg": _round_maybe(_average(recall_values), 4),
            "mrr_avg": _round_maybe(_average(mrr_values), 4),
            "ndcg_avg": _round_maybe(_average(ndcg_values), 4),
        },
        "samples": {
            "total": len(rows),
            "chat": len(chat_rows),
            "ingest": len(ingest_rows),
        },
    }
