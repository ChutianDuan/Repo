import json
from typing import Any, Dict

from python_rag.app.agent.tools.local.knowledge_tools import KNOWLEDGE_SEARCH_TOOL_NAME


KNOWLEDGE_SEARCH_ROUTER_REASON = "project_document_code_intent"

_STRONG_INTENT_TERMS = (
    "项目文档", "项目资料", "知识库", "文档里", "文档中", "上传文档",
    "上传网页", "网页上传", "导入网页", "项目架构", "系统架构", "代码库",
    "当前项目", "这个项目", "agent项目", "embedding", "向量化", "向量库",
    "project docs", "project document", "knowledge base", "codebase",
    "source code", "web ingest", "web page", "webpage", "url import",
    "vector index",
)
_TOPIC_TERMS = (
    "项目", "文档", "资料", "代码", "源码", "架构", "模块", "实现", "能力",
    "功能", "上传", "导入", "网页", "索引", "分块", "检索", "召回", "引用",
    "project", "document", "docs", "code", "architecture", "module",
    "implementation", "capability", "feature", "upload", "import", "ingest",
    "retrieval", "index", "chunk", "citation",
)
_CONTEXT_TERMS = (
    "项目", "系统", "agent", "当前", "这个", "本地", "project", "system",
    "this", "current", "local",
)
_INTENT_TERMS = (
    "怎么", "如何", "为什么", "是否", "有没有", "能否", "支持", "总结", "说明",
    "解释", "介绍", "查询", "查看", "列出", "有哪些", "优化", "实现", "流程",
    "设计", "what", "how", "why", "whether", "does", "do ", "can ",
    "support", "explain", "summarize", "list", "show", "optimize",
    "implement", "design",
)


def should_force_knowledge_search(question: str) -> bool:
    normalized = " ".join(str(question or "").strip().lower().split())
    if not normalized:
        return False
    if any(term in normalized for term in _STRONG_INTENT_TERMS):
        return True
    if not any(term in normalized for term in _TOPIC_TERMS):
        return False
    return (
        any(term in normalized for term in _CONTEXT_TERMS)
        or any(term in normalized for term in _INTENT_TERMS)
    )


def build_forced_knowledge_search_tool_call(question: str) -> Dict[str, Any]:
    return {
        "id": "forced_knowledge_search_0",
        "type": "function",
        "function": {
            "name": KNOWLEDGE_SEARCH_TOOL_NAME,
            "arguments": json.dumps({"query": question}, ensure_ascii=False),
        },
    }


__all__ = [
    "KNOWLEDGE_SEARCH_ROUTER_REASON",
    "build_forced_knowledge_search_tool_call",
    "should_force_knowledge_search",
]
