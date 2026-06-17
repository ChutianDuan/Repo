from typing import Any, Dict, List, Optional

from python_rag.app.agent.agent_runner import AgentRunExecutor
from python_rag.app.agent.orchestration_config import (
    AgentEventSink,
    AgentOrchestratorError,
    DEFAULT_AGENT_NAME,
    DEFAULT_MAX_STEPS,
    READONLY_PERMISSION_LEVEL,
    READONLY_TOOL_NAMES,
    SYSTEM_PROMPT,
)
from python_rag.app.agent.memory import session as session_memory
from python_rag.app.agent.trace import trace_service
from python_rag.app.agent.tools.registry import ToolRegistry, default_registry
from python_rag.app.modules.llm import service as llm_service


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

    async def run(
        self,
        question: str,
        trace_id: Optional[str] = None,
        session_id: Optional[int] = None,
        user_message_id: Optional[int] = None,
        event_sink: Optional[AgentEventSink] = None,
    ) -> Dict[str, Any]:
        runner = AgentRunExecutor(
            orchestrator=self,
            trace_service_module=trace_service,
            llm_service_module=llm_service,
        )
        return await runner.run(
            question=question,
            trace_id=trace_id,
            session_id=session_id,
            user_message_id=user_message_id,
            event_sink=event_sink,
        )


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
    "AgentEventSink",
    "AgentOrchestrator",
    "AgentOrchestratorError",
    "DEFAULT_AGENT_NAME",
    "DEFAULT_MAX_STEPS",
    "READONLY_PERMISSION_LEVEL",
    "READONLY_TOOL_NAMES",
    "SYSTEM_PROMPT",
    "run_agent",
]
