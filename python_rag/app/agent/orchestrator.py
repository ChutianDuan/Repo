import inspect
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from python_rag.app.agent.trace import trace_service
from python_rag.app.agent.memory import session as session_memory
from python_rag.app.agent.schemas import AgentStepStatus, AgentToolCallStatus
from python_rag.app.agent.tools.local.citation_tools import (
    LIST_MESSAGE_CITATIONS_TOOL_NAME,
)
from python_rag.app.agent.tools.local.document_tools import (
    DOCUMENT_DETAIL_TOOL_NAME,
    LIST_READY_DOCUMENTS_TOOL_NAME,
)
from python_rag.app.agent.tools.local.knowledge_tools import KNOWLEDGE_SEARCH_TOOL_NAME
from python_rag.app.agent.tools.registry import ToolRegistry, default_registry
from python_rag.app.modules.llm import service as llm_service


DEFAULT_AGENT_NAME = "rag-agent"
DEFAULT_MAX_STEPS = 3
READONLY_PERMISSION_LEVEL = "readonly"
READONLY_TOOL_NAMES = [
    KNOWLEDGE_SEARCH_TOOL_NAME,
    DOCUMENT_DETAIL_TOOL_NAME,
    LIST_READY_DOCUMENTS_TOOL_NAME,
    LIST_MESSAGE_CITATIONS_TOOL_NAME,
]
SYSTEM_PROMPT = (
    "你是一个本地知识库检索智能体。"
    "你的任务是判断用户问题是否需要项目知识库证据，并基于检索结果给出回答。"
    "当需要补充上下文时，只能使用只读工具。"
    "只能调用已注册、可用的工具，禁止编造工具名称或假设不存在的能力。"
    "如果用户只是问候、闲聊或提出不依赖项目文档的简单问题，直接回答，不要调用工具。"
    "如果用户询问项目文档、系统架构、模块、实现细节或文档中是否存在某能力，必须先调用 knowledge_search。"
    "如果用户要求根据 document_id 查询文档详情，必须调用 get_document_detail。"
    "如果用户询问当前知识库有哪些文档、能问哪些资料或哪些文档已经建好索引，必须调用 list_ready_documents。"
    "如果用户要求按 message_id 查看某条 assistant 消息的已保存引用或 citations，必须调用 list_message_citations。"
    "如果 knowledge_search 没有返回结果，应明确说明当前知识库证据不足，不要编造。"
    "如果 knowledge_search 返回 error，应说明检索工具失败并给出降级说明，不要编造文档结论。"
    "获取工具结果后，应判断证据是否足够；足够时回答用户问题，不足时可继续调用只读工具补充上下文。"
    "避免重复发起相同或无意义的工具调用。"
    "如果工具结果中包含有用的文档标题，应在回答中引用这些标题。"
)
AgentEventSink = Callable[[Dict[str, Any]], Any]
logger = logging.getLogger(__name__)


class AgentOrchestratorError(Exception):
    pass


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


async def _emit_agent_event(
    event_sink: Optional[AgentEventSink],
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
    system_prompt: str = SYSTEM_PROMPT,
    memory: Optional[session_memory.SessionMemory] = None,
) -> List[Dict[str, Any]]:
    return session_memory.build_agent_messages(
        system_prompt=system_prompt,
        question=question,
        memory=memory,
    )


class AgentOrchestrator:
    def __init__(
        self,
        registry: ToolRegistry = default_registry,
        max_steps: int = DEFAULT_MAX_STEPS,
        agent_name: str = DEFAULT_AGENT_NAME,
    ):
        self.registry = registry
        self.max_steps = max(1, int(max_steps or DEFAULT_MAX_STEPS))
        self.agent_name = agent_name

    def _readonly_tool_names(self) -> List[str]:
        "获取只读工具名单，且必须在注册表中存在"
        return [
            name
            for name in READONLY_TOOL_NAMES
            if self.registry.has(name)
        ]

    def _tool_schemas(self) -> List[dict]:
        "获取工具输入格式，且必须在注册表中存在且权限符合要求"
        return self.registry.export_openai_tools_schema(
            names=self._readonly_tool_names(),
            permission_level=READONLY_PERMISSION_LEVEL,
        )

    def _get_readonly_tool(self, name: str):
        if name not in READONLY_TOOL_NAMES:
            raise AgentOrchestratorError("tool is not allowed: {0}".format(name))

        tool = self.registry.get(name)
        if tool.permission_level != READONLY_PERMISSION_LEVEL:
            raise AgentOrchestratorError(
                "tool permission denied: {0}".format(name)
            )
        return tool

    async def _execute_tool_call(
        self,
        run_id: int,
        step_id: int,
        tool_call: Dict[str, Any],
        fallback_index: int,
        event_sink: Optional[AgentEventSink] = None,
    ) -> Dict[str, Any]:
        external_tool_call_id = _tool_call_id(tool_call, fallback_index)
        tool_name = _tool_call_name(tool_call)

        try:
            arguments = _parse_tool_arguments(tool_call)
        except Exception as exc:
            arguments = {}
            tool_row_id = trace_service.create_tool_call(
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
            trace_service.fail_tool_call(
                tool_call_id=tool_row_id,
                error_message=str(exc),
                result=result,
                result_preview=trace_service.build_tool_result_preview(tool_name or "unknown", result),
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

        tool_row_id = trace_service.create_tool_call(
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

        started_at = time.time()
        try:
            tool = self._get_readonly_tool(tool_name)
            result = await tool.run(arguments)
            latency_ms = int((time.time() - started_at) * 1000)
            error_message = _tool_result_error(result)
            if error_message:
                trace_service.fail_tool_call(
                    tool_call_id=tool_row_id,
                    error_message=error_message,
                    result=result,
                    result_preview=trace_service.build_tool_result_preview(tool_name, result),
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

            trace_service.finish_tool_call(
                tool_call_id=tool_row_id,
                result=result,
                result_preview=trace_service.build_tool_result_preview(tool_name, result),
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
            trace_service.fail_tool_call(
                tool_call_id=tool_row_id,
                error_message=str(exc),
                result=result,
                result_preview=trace_service.build_tool_result_preview(tool_name, result),
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
        event_sink: Optional[AgentEventSink] = None,
    ) -> Dict[str, Any]:
        question = str(question or "").strip()
        if not question:
            raise AgentOrchestratorError("question is required")

        # 读取会话记忆；后续构造 messages 时会注入摘要和最近对话。
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

        run_id = trace_service.create_run(
            agent_name=self.agent_name,
            trace_id=trace_id,
            session_id=session_id,
            user_message_id=user_message_id,
            input_data={"question": question},
            meta={
                "max_steps": self.max_steps,
                "tools": self._readonly_tool_names(),
                "permission_level": READONLY_PERMISSION_LEVEL,
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
        # 初始 messages 包含 system prompt、会话记忆和当前 question。
        messages = _build_initial_messages(
            question,
            memory=memory,
        )
        tool_schemas = self._tool_schemas()
        observations: List[Dict[str, Any]] = []
        run_closed = False

        try:
            for step_index in range(self.max_steps):
                step_name = "agent_step_{0}".format(step_index)
                step_type = "llm_decision"
                # 每轮都暴露只读工具，让 agent 自己决定继续调工具还是结束回答。
                effective_tool_schemas = tool_schemas
                effective_tool_choice = "auto" if effective_tool_schemas is not None else None
                step_id = trace_service.create_step(
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
                # 循环调用 LLM：messages 会累积 question、assistant 工具请求和 tool 结果。
                llm_result = llm_service.generate_from_messages(
                    messages,
                    tools=effective_tool_schemas,
                    tool_choice=effective_tool_choice,
                )
                # 解析本轮 LLM 决策；没有 tool_calls 表示 agent 选择输出最终答案。
                usage = _extract_usage(llm_result)
                tool_calls = llm_result.get("tool_calls") or []

                if not tool_calls:
                    final_answer = str(
                        llm_result.get("answer")
                        or (llm_result.get("message") or {}).get("content")
                        or ""
                    ).strip()
                    trace_service.finish_step(
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
                    trace_service.finish_run(
                        run_id=run_id,
                        output_data={
                            "answer": final_answer,
                            "observations": observations,
                            "citations": citations,
                            "retrieval": retrieval,
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
                    }

                # 先记录 assistant 的工具请求，下一条 tool 消息需要与 tool_call_id 配对。
                assistant_message = {
                    "role": "assistant",
                    "content": (llm_result.get("message") or {}).get("content") or "",
                    "tool_calls": tool_calls,
                }
                messages.append(assistant_message)

                step_observations = []
                for call_index, tool_call in enumerate(tool_calls):
                    # 执行工具调用，并把原始结果保存为 observation 供 trace 和引用提取使用。
                    observation = await self._execute_tool_call(
                        run_id=run_id,
                        step_id=step_id,
                        tool_call=tool_call,
                        fallback_index=call_index,
                        event_sink=event_sink,
                    )
                    observations.append(observation)
                    step_observations.append(observation)
                    # 工具结果追加到 messages，相当于把检索结果加入上下文给下一轮 LLM 判断。
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": observation["tool_call_id"],
                            "name": observation["tool_name"],
                            "content": _json_dumps(observation["result"]),
                        }
                    )

                trace_service.finish_step(
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

            error_message = "agent reached max_steps without final answer"
            trace_service.fail_run(
                run_id=run_id,
                error_message=error_message,
                output_data={
                    "observations": observations,
                },
            )
            run_closed = True
            raise AgentOrchestratorError(error_message)
        except Exception as exc:
            if not run_closed:
                trace_service.fail_run(
                    run_id=run_id,
                    error_message=str(exc),
                    output_data={
                        "observations": observations,
                    },
                )
            raise


async def run_agent(
    question: str,
    trace_id: Optional[str] = None,
    session_id: Optional[int] = None,
    user_message_id: Optional[int] = None,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> Dict[str, Any]:
    orchestrator = AgentOrchestrator(max_steps=max_steps)
    return await orchestrator.run(
        question=question,
        trace_id=trace_id,
        session_id=session_id,
        user_message_id=user_message_id,
    )


__all__ = [
    "AgentOrchestrator",
    "AgentOrchestratorError",
    "DEFAULT_AGENT_NAME",
    "DEFAULT_MAX_STEPS",
    "READONLY_PERMISSION_LEVEL",
    "READONLY_TOOL_NAMES",
    "run_agent",
]
