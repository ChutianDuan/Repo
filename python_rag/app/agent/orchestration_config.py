from typing import Any, Callable, Dict

from python_rag.app.agent.tools.local.citation_tools import (
    LIST_MESSAGE_CITATIONS_TOOL_NAME,
)
from python_rag.app.agent.tools.local.document_tools import (
    DOCUMENT_DETAIL_TOOL_NAME,
    LIST_READY_DOCUMENTS_TOOL_NAME,
)
from python_rag.app.agent.tools.local.knowledge_tools import KNOWLEDGE_SEARCH_TOOL_NAME


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


class AgentOrchestratorError(Exception):
    pass


__all__ = [
    "AgentEventSink",
    "AgentOrchestratorError",
    "DEFAULT_AGENT_NAME",
    "DEFAULT_MAX_STEPS",
    "READONLY_PERMISSION_LEVEL",
    "READONLY_TOOL_NAMES",
    "SYSTEM_PROMPT",
]
