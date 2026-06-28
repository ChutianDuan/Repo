import inspect
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from python_rag.app.agent import orchestration_config as config
from python_rag.app.agent.memory import session as session_memory
from python_rag.app.agent.schemas import AgentStepStatus, AgentToolCallStatus
from python_rag.app.agent.tools.local.knowledge_tools import KNOWLEDGE_SEARCH_TOOL_NAME
from python_rag.app.agent.trace import trace_service as default_trace_service
from python_rag.app.modules.llm import service as default_llm_service


logger = logging.getLogger("python_rag.app.agent.orchestrator")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


async def _emit_agent_event(
    event_sink: Optional[config.AgentEventSink],
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    if event_sink is None:
        return

    event = dict(payload)
    event["type"] = event_type
    result = event_sink(event)
    if inspect.isawaitable(result):
        await result


def _extract_usage(result: Dict[str, Any]) -> Dict[str, Optional[int]]:
    usage = result.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens")
    if prompt_tokens is None:
        prompt_tokens = usage.get("input_tokens")

    completion_tokens = usage.get("completion_tokens")
    if completion_tokens is None:
        completion_tokens = usage.get("output_tokens")

    total_tokens = usage.get("total_tokens")
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _parse_tool_arguments(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    function = tool_call.get("function") or {}
    raw_arguments = function.get("arguments")
    if raw_arguments is None or raw_arguments == "":
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not isinstance(raw_arguments, str):
        raise ValueError("tool arguments must be a JSON object")

    parsed = json.loads(raw_arguments)
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments must be a JSON object")
    return parsed


def _tool_call_name(tool_call: Dict[str, Any]) -> str:
    function = tool_call.get("function") or {}
    return str(function.get("name") or "").strip()


def _tool_call_id(tool_call: Dict[str, Any], fallback_index: int) -> str:
    return str(tool_call.get("id") or "tool_call_{0}".format(fallback_index))


def _tool_result_error(result: Any) -> Optional[str]:
    if not isinstance(result, dict):
        return None
    error = result.get("error")
    if error is None:
        return None
    error_message = str(error).strip()
    return error_message or None


def _tool_call_signature(tool_name: str, arguments: Dict[str, Any]) -> str:
    return "{0}:{1}".format(
        tool_name,
        json.dumps(arguments or {}, ensure_ascii=False, sort_keys=True),
    )


def _coerce_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_score(value: Any) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def _extract_observation_citations(
    observations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    seen: Set[Tuple[int, int]] = set()

    for observation in observations:
        if observation.get("tool_name") != KNOWLEDGE_SEARCH_TOOL_NAME:
            continue

        result = observation.get("result")
        if not isinstance(result, dict):
            continue

        results = result.get("results") or []
        if not isinstance(results, list):
            continue

        for item in results:
            if not isinstance(item, dict):
                continue

            doc_id_value = item.get("doc_id")
            if doc_id_value is None:
                doc_id_value = item.get("document_id")
            chunk_index_value = item.get("chunk_index")
            if chunk_index_value is None:
                chunk_index_value = item.get("index", item.get("seq"))

            doc_id = _coerce_int(doc_id_value)
            chunk_id = _coerce_int(item.get("chunk_id") or item.get("id"))
            chunk_index = _coerce_int(chunk_index_value)
            if doc_id is None or chunk_id is None or chunk_index is None:
                continue

            key = (doc_id, chunk_id)
            if key in seen:
                continue
            seen.add(key)

            content = str(item.get("content") or item.get("snippet") or "")
            citations.append(
                {
                    "rank": len(citations) + 1,
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                    "score": _coerce_score(item.get("score")),
                    "snippet": str(item.get("snippet") or content)[:300],
                    "content": content,
                    "title": item.get("title") or "",
                }
            )

    return citations


def _extract_observation_retrieval_summary(
    observations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for observation in observations:
        if observation.get("tool_name") != KNOWLEDGE_SEARCH_TOOL_NAME:
            continue

        result = observation.get("result")
        if not isinstance(result, dict):
            continue

        retrieval = result.get("retrieval")
        if isinstance(retrieval, dict):
            summary = dict(retrieval)
            total = result.get("total")
            if total is not None:
                summary["retrieved_count"] = total
    return summary


def _build_initial_messages(
    question: str,
    system_prompt: str = config.SYSTEM_PROMPT,
    memory: Optional[session_memory.SessionMemory] = None,
) -> List[Dict[str, Any]]:
    return session_memory.build_agent_messages(
        system_prompt=system_prompt,
        question=question,
        memory=memory,
    )


class AgentRunExecutor:
    """Runs the agent decision loop for an AgentOrchestrator facade."""

    def __init__(
        self,
        orchestrator: Any,
        trace_service_module: Any = default_trace_service,
        llm_service_module: Any = default_llm_service,
    ):
        self.orchestrator = orchestrator
        self.trace_service = trace_service_module
        self.llm_service = llm_service_module

    async def _execute_tool_call(
        self,
        run_id: int,
        step_id: int,
        tool_call: Dict[str, Any],
        fallback_index: int,
        event_sink: Optional[config.AgentEventSink] = None,
        seen_tool_calls: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        external_tool_call_id = _tool_call_id(tool_call, fallback_index)
        tool_name = _tool_call_name(tool_call)

        try:
            arguments = _parse_tool_arguments(tool_call)
        except Exception as exc:
            arguments = {}
            tool_row_id = self.trace_service.create_tool_call(
                run_id=run_id,
                step_id=step_id,
                tool_name=tool_name or "unknown",
                arguments=arguments,
                tool_call_id=external_tool_call_id,
            )
            await _emit_agent_event(
                event_sink,
                "tool_call",
                {
                    "run_id": run_id,
                    "step_id": step_id,
                    "tool_call_row_id": tool_row_id,
                    "tool_call_id": external_tool_call_id,
                    "tool_name": tool_name or "unknown",
                    "arguments": arguments,
                    "status": AgentToolCallStatus.RUNNING,
                },
            )
            result = {
                "results": [],
                "total": 0,
                "error": str(exc),
            }
            self.trace_service.fail_tool_call(
                tool_call_id=tool_row_id,
                error_message=str(exc),
                result=result,
                result_preview=self.trace_service.build_tool_result_preview(
                    tool_name or "unknown",
                    result,
                ),
            )
            await _emit_agent_event(
                event_sink,
                "tool_result",
                {
                    "run_id": run_id,
                    "step_id": step_id,
                    "tool_call_row_id": tool_row_id,
                    "tool_call_id": external_tool_call_id,
                    "tool_name": tool_name or "unknown",
                    "arguments": arguments,
                    "result": result,
                    "status": AgentToolCallStatus.FAILED,
                    "error_message": str(exc),
                },
            )
            return {
                "tool_call_id": external_tool_call_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "error": str(exc),
            }

        duplicate_error = None
        if seen_tool_calls is not None:
            signature = _tool_call_signature(tool_name, arguments)
            if signature in seen_tool_calls:
                duplicate_error = "duplicate tool call skipped: {0}".format(
                    tool_name or "unknown"
                )
            else:
                seen_tool_calls.add(signature)

        tool_row_id = self.trace_service.create_tool_call(
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            arguments=arguments,
            tool_call_id=external_tool_call_id,
        )
        await _emit_agent_event(
            event_sink,
            "tool_call",
            {
                "run_id": run_id,
                "step_id": step_id,
                "tool_call_row_id": tool_row_id,
                "tool_call_id": external_tool_call_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "status": AgentToolCallStatus.RUNNING,
            },
        )

        if duplicate_error:
            result = {
                "skipped": True,
                "reason": "duplicate_tool_call",
                "error": duplicate_error,
            }
            self.trace_service.fail_tool_call(
                tool_call_id=tool_row_id,
                error_message=duplicate_error,
                result=result,
                result_preview=self.trace_service.build_tool_result_preview(
                    tool_name or "unknown",
                    result,
                ),
                latency_ms=0,
            )
            await _emit_agent_event(
                event_sink,
                "tool_result",
                {
                    "run_id": run_id,
                    "step_id": step_id,
                    "tool_call_row_id": tool_row_id,
                    "tool_call_id": external_tool_call_id,
                    "tool_name": tool_name or "unknown",
                    "arguments": arguments,
                    "result": result,
                    "status": AgentToolCallStatus.FAILED,
                    "error_message": duplicate_error,
                    "latency_ms": 0,
                },
            )
            return {
                "tool_call_id": external_tool_call_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "error": duplicate_error,
            }

        started_at = time.time()
        try:
            tool = self.orchestrator._get_readonly_tool(tool_name)
            result = await tool.run(arguments)
            latency_ms = int((time.time() - started_at) * 1000)
            error_message = _tool_result_error(result)
            if error_message:
                self.trace_service.fail_tool_call(
                    tool_call_id=tool_row_id,
                    error_message=error_message,
                    result=result,
                    result_preview=self.trace_service.build_tool_result_preview(
                        tool_name,
                        result,
                    ),
                    latency_ms=latency_ms,
                )
                await _emit_agent_event(
                    event_sink,
                    "tool_result",
                    {
                        "run_id": run_id,
                        "step_id": step_id,
                        "tool_call_row_id": tool_row_id,
                        "tool_call_id": external_tool_call_id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result": result,
                        "status": AgentToolCallStatus.FAILED,
                        "error_message": error_message,
                        "latency_ms": latency_ms,
                    },
                )
                return {
                    "tool_call_id": external_tool_call_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "error": error_message,
                }

            self.trace_service.finish_tool_call(
                tool_call_id=tool_row_id,
                result=result,
                result_preview=self.trace_service.build_tool_result_preview(
                    tool_name,
                    result,
                ),
                latency_ms=latency_ms,
            )
            await _emit_agent_event(
                event_sink,
                "tool_result",
                {
                    "run_id": run_id,
                    "step_id": step_id,
                    "tool_call_row_id": tool_row_id,
                    "tool_call_id": external_tool_call_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "status": AgentToolCallStatus.SUCCESS,
                    "latency_ms": latency_ms,
                },
            )
            return {
                "tool_call_id": external_tool_call_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
            }
        except Exception as exc:
            result = {
                "results": [],
                "total": 0,
                "error": str(exc),
            }
            self.trace_service.fail_tool_call(
                tool_call_id=tool_row_id,
                error_message=str(exc),
                result=result,
                result_preview=self.trace_service.build_tool_result_preview(
                    tool_name,
                    result,
                ),
                latency_ms=int((time.time() - started_at) * 1000),
            )
            await _emit_agent_event(
                event_sink,
                "tool_result",
                {
                    "run_id": run_id,
                    "step_id": step_id,
                    "tool_call_row_id": tool_row_id,
                    "tool_call_id": external_tool_call_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "status": AgentToolCallStatus.FAILED,
                    "error_message": str(exc),
                },
            )
            return {
                "tool_call_id": external_tool_call_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "error": str(exc),
            }

    async def run(
        self,
        question: str,
        trace_id: Optional[str] = None,
        session_id: Optional[int] = None,
        user_message_id: Optional[int] = None,
        event_sink: Optional[config.AgentEventSink] = None,
    ) -> Dict[str, Any]:
        question = str(question or "").strip()
        if not question:
            raise config.AgentOrchestratorError("question is required")

        memory = session_memory.load_session_memory(
            session_id=session_id,
            current_user_message_id=user_message_id,
        )
        memory_debug_context = session_memory.format_memory_debug_context(memory)
        if memory_debug_context:
            logger.info(
                "agent memory context session_id=%s user_id=%s user_message_id=%s message_count=%s user_memory_message_id=%s user_memory_task_queued=%s summary_message_id=%s summary_task_queued=%s\n%s",
                session_id,
                memory.user_id,
                user_message_id,
                memory.message_count,
                memory.user_memory_message_id,
                memory.user_memory_task_queued,
                memory.summary_message_id,
                memory.summary_task_queued,
                memory_debug_context,
            )

        run_id = self.trace_service.create_run(
            agent_name=self.orchestrator.agent_name,
            trace_id=trace_id,
            session_id=session_id,
            user_message_id=user_message_id,
            input_data={"question": question},
            meta={
                "max_steps": self.orchestrator.max_steps,
                "tools": self.orchestrator._readonly_tool_names(),
                "permission_level": config.READONLY_PERMISSION_LEVEL,
                "memory": {
                    "user_id": memory.user_id,
                    "message_count": memory.message_count,
                    "recent_message_count": len(memory.recent_messages),
                    "has_user_memory": bool(memory.user_memory),
                    "user_memory_message_id": memory.user_memory_message_id,
                    "user_memory_task_queued": memory.user_memory_task_queued,
                    "user_memory_updated": memory.user_memory_updated,
                    "has_summary": bool(memory.summary),
                    "summary_message_id": memory.summary_message_id,
                    "summary_task_queued": memory.summary_task_queued,
                    "summary_updated": memory.summary_updated,
                },
            },
        )
        messages = _build_initial_messages(
            question,
            memory=memory,
        )
        tool_schemas = self.orchestrator._tool_schemas()
        observations: List[Dict[str, Any]] = []
        seen_tool_calls: Set[str] = set()
        run_closed = False

        try:
            step_index = 0
            while step_index < self.orchestrator.max_steps:
                step_name = "agent_step_{0}".format(step_index)
                step_type = "llm_decision"
                effective_tool_schemas = tool_schemas or None
                effective_tool_choice = (
                    "auto" if effective_tool_schemas is not None else None
                )
                step_id = self.trace_service.create_step(
                    run_id=run_id,
                    step_index=step_index,
                    step_type=step_type,
                    name=step_name,
                    input_data={
                        "messages": messages,
                        "tools": effective_tool_schemas,
                    },
                )
                await _emit_agent_event(
                    event_sink,
                    "agent_step",
                    {
                        "run_id": run_id,
                        "step_id": step_id,
                        "step_index": step_index,
                        "step_type": step_type,
                        "name": step_name,
                        "status": AgentStepStatus.RUNNING,
                    },
                )
                llm_result = self.llm_service.generate_from_messages(
                    messages,
                    tools=effective_tool_schemas,
                    tool_choice=effective_tool_choice,
                )
                usage = _extract_usage(llm_result)
                tool_calls = llm_result.get("tool_calls") or []

                if not tool_calls:
                    final_answer = str(
                        llm_result.get("answer")
                        or (llm_result.get("message") or {}).get("content")
                        or ""
                    ).strip()
                    self.trace_service.finish_step(
                        step_id=step_id,
                        output_data={
                            "answer": final_answer,
                            "llm": llm_result,
                        },
                        decision="final_answer",
                        prompt_tokens=usage["prompt_tokens"],
                        completion_tokens=usage["completion_tokens"],
                        total_tokens=usage["total_tokens"],
                        latency_ms=llm_result.get("latency_ms"),
                    )
                    await _emit_agent_event(
                        event_sink,
                        "agent_step",
                        {
                            "run_id": run_id,
                            "step_id": step_id,
                            "step_index": step_index,
                            "step_type": step_type,
                            "name": step_name,
                            "status": AgentStepStatus.SUCCESS,
                            "decision": "final_answer",
                            "answer": final_answer,
                        },
                    )
                    citations = _extract_observation_citations(observations)
                    retrieval = _extract_observation_retrieval_summary(observations)
                    self.trace_service.finish_run(
                        run_id=run_id,
                        output_data={
                            "answer": final_answer,
                            "observations": observations,
                            "citations": citations,
                            "retrieval": retrieval,
                            "termination_reason": "final_answer",
                        },
                    )
                    run_closed = True
                    return {
                        "run_id": run_id,
                        "answer": final_answer,
                        "messages": messages,
                        "observations": observations,
                        "citations": citations,
                        "retrieval": retrieval,
                        "steps_used": step_index + 1,
                        "termination_reason": "final_answer",
                    }

                assistant_message = {
                    "role": "assistant",
                    "content": (llm_result.get("message") or {}).get("content") or "",
                    "tool_calls": tool_calls,
                }
                messages.append(assistant_message)

                step_observations = []
                for call_index, tool_call in enumerate(tool_calls):
                    observation = await self._execute_tool_call(
                        run_id=run_id,
                        step_id=step_id,
                        tool_call=tool_call,
                        fallback_index=call_index,
                        event_sink=event_sink,
                        seen_tool_calls=seen_tool_calls,
                    )
                    observations.append(observation)
                    step_observations.append(observation)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": observation["tool_call_id"],
                            "name": observation["tool_name"],
                            "content": _json_dumps(observation["result"]),
                        }
                    )

                self.trace_service.finish_step(
                    step_id=step_id,
                    output_data={
                        "llm": llm_result,
                        "observations": step_observations,
                    },
                    decision="tool_call",
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                    total_tokens=usage["total_tokens"],
                    latency_ms=llm_result.get("latency_ms"),
                )
                await _emit_agent_event(
                    event_sink,
                    "agent_step",
                    {
                        "run_id": run_id,
                        "step_id": step_id,
                        "step_index": step_index,
                        "step_type": step_type,
                        "name": step_name,
                        "status": AgentStepStatus.SUCCESS,
                        "decision": "tool_call",
                        "tool_call_count": len(step_observations),
                    },
                )
                step_index += 1

            error_message = "agent reached max_steps without final answer"
            self.trace_service.fail_run(
                run_id=run_id,
                error_message=error_message,
                output_data={
                    "observations": observations,
                    "steps_used": step_index,
                    "termination_reason": "max_steps",
                },
            )
            run_closed = True
            raise config.AgentOrchestratorError(error_message)
        except Exception as exc:
            if not run_closed:
                self.trace_service.fail_run(
                    run_id=run_id,
                    error_message=str(exc),
                    output_data={
                        "observations": observations,
                    },
                )
            raise


__all__ = ["AgentRunExecutor"]
