import json
from typing import Any, Optional

from python_rag.app.agent import models
from python_rag.app.agent.schemas import (
    AgentRunStatus,
    AgentStepStatus,
    AgentToolCallStatus,
)


_UNSET = object()
_PREVIEW_MAX_CHARS = 2000

__all__ = [
    "create_run",
    "finish_run",
    "fail_run",
    "create_step",
    "finish_step",
    "create_tool_call",
    "finish_tool_call",
    "fail_tool_call",
    "build_tool_result_preview",
]


def _total_tokens(
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    total_tokens: Optional[int],
) -> Optional[int]:
    if total_tokens is not None:
        return total_tokens
    if prompt_tokens is None or completion_tokens is None:
        return None
    return prompt_tokens + completion_tokens


def _preview(value: Any) -> Optional[str]:
    if value is _UNSET or value is None:
        return None
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    return text[:_PREVIEW_MAX_CHARS]


def _model_value(value: Any) -> Any:
    if value is _UNSET:
        return models._UNSET
    return value


def build_tool_result_preview(tool_name: str, result: Any) -> Optional[str]:
    if not isinstance(result, dict):
        return _preview(result)

    preview_value = result
    if {"ok", "error", "data"}.issubset(set(result.keys())):
        data = result.get("data")
        if result.get("ok") is True and isinstance(data, dict):
            preview_value = data

    if tool_name == "knowledge_search":
        retrieval = preview_value.get("retrieval") or {}
        parts = []
        total = preview_value.get("total")
        if total is not None:
            parts.append("total={0}".format(total))
        provider = retrieval.get("provider")
        if provider:
            parts.append("provider={0}".format(provider))
        dense_top_k = retrieval.get("dense_top_k")
        if dense_top_k is not None:
            parts.append("dense_top_k={0}".format(dense_top_k))
        rerank_top_k = retrieval.get("rerank_top_k")
        if rerank_top_k is not None:
            parts.append("rerank_top_k={0}".format(rerank_top_k))
        candidate_count = retrieval.get("candidate_count")
        if candidate_count is not None:
            parts.append("candidates={0}".format(candidate_count))
        vector_ms = retrieval.get("vector_search_latency_ms")
        if vector_ms is not None:
            parts.append("vector_ms={0}".format(vector_ms))
        rerank_ms = retrieval.get("rerank_latency_ms")
        if rerank_ms is not None:
            parts.append("rerank_ms={0}".format(rerank_ms))
        retrieval_ms = retrieval.get("retrieval_latency_ms")
        if retrieval_ms is not None:
            parts.append("retrieval_ms={0}".format(retrieval_ms))
        if parts:
            return "; ".join(parts)[:_PREVIEW_MAX_CHARS]

    return _preview(preview_value)


def create_run(
    agent_name: str,
    input_data: Any = None,
    trace_id: Optional[str] = None,
    agent_version: Optional[str] = None,
    model: Optional[str] = None,
    session_id: Optional[int] = None,
    user_message_id: Optional[int] = None,
    meta: Any = None,
) -> int:
    return models.create_agent_run(
        agent_name=agent_name,
        trace_id=trace_id,
        agent_version=agent_version,
        model=model,
        status=AgentRunStatus.RUNNING,
        session_id=session_id,
        user_message_id=user_message_id,
        input_data=input_data,
        meta=meta,
    )


def finish_run(
    run_id: int,
    output_data: Any = _UNSET,
    meta: Any = _UNSET,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
) -> None:
    models.update_agent_run(
        run_id=run_id,
        status=AgentRunStatus.SUCCESS,
        output_data=_model_value(output_data),
        meta=_model_value(meta),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=_total_tokens(prompt_tokens, completion_tokens, total_tokens),
        cost_usd=cost_usd,
        error_message=None,
        finished=True,
    )


def fail_run(
    run_id: int,
    error_message: str,
    output_data: Any = _UNSET,
    meta: Any = _UNSET,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
) -> None:
    models.update_agent_run(
        run_id=run_id,
        status=AgentRunStatus.FAILED,
        output_data=_model_value(output_data),
        meta=_model_value(meta),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=_total_tokens(prompt_tokens, completion_tokens, total_tokens),
        cost_usd=cost_usd,
        error_message=error_message,
        finished=True,
    )


def create_step(
    run_id: int,
    step_index: Optional[int] = None,
    step_type: str = "decision",
    name: Optional[str] = None,
    model: Optional[str] = None,
    input_data: Any = None,
    reasoning_summary: Optional[str] = None,
    decision: Optional[str] = None,
) -> int:
    if step_index is None:
        step_index = models.get_next_agent_step_index(run_id)

    return models.create_agent_step(
        run_id=run_id,
        step_index=step_index,
        step_type=step_type,
        name=name,
        status=AgentStepStatus.RUNNING,
        model=model,
        input_data=input_data,
        reasoning_summary=reasoning_summary,
        decision=decision,
    )


def finish_step(
    step_id: int,
    output_data: Any = _UNSET,
    reasoning_summary: Any = _UNSET,
    decision: Any = _UNSET,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    latency_ms: Optional[int] = None,
) -> None:
    models.update_agent_step(
        step_id=step_id,
        status=AgentStepStatus.SUCCESS,
        reasoning_summary=_model_value(reasoning_summary),
        decision=_model_value(decision),
        output_data=_model_value(output_data),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=_total_tokens(prompt_tokens, completion_tokens, total_tokens),
        latency_ms=latency_ms,
        error_message=None,
        finished=True,
    )


def create_tool_call(
    run_id: int,
    step_id: int,
    tool_name: str,
    arguments: Any = None,
    tool_call_id: Optional[str] = None,
) -> int:
    return models.create_agent_tool_call(
        run_id=run_id,
        step_id=step_id,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        status=AgentToolCallStatus.RUNNING,
        arguments=arguments,
    )


def finish_tool_call(
    tool_call_id: int,
    result: Any = _UNSET,
    result_preview: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> None:
    if result_preview is None:
        result_preview = _preview(result)

    models.update_agent_tool_call(
        tool_call_row_id=tool_call_id,
        status=AgentToolCallStatus.SUCCESS,
        result=_model_value(result),
        result_preview=result_preview,
        latency_ms=latency_ms,
        error_message=None,
        finished=True,
    )


def fail_tool_call(
    tool_call_id: int,
    error_message: str,
    result: Any = _UNSET,
    result_preview: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> None:
    if result_preview is None:
        result_preview = _preview(result)

    models.update_agent_tool_call(
        tool_call_row_id=tool_call_id,
        status=AgentToolCallStatus.FAILED,
        result=_model_value(result),
        result_preview=result_preview,
        latency_ms=latency_ms,
        error_message=error_message,
        finished=True,
    )
