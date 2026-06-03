from typing import Any, Dict, Optional

from python_rag.app.agent.tools.base import BaseTool
from python_rag.app.agent.tools.registry import ToolRegistry, default_registry


KNOWLEDGE_SEARCH_TOOL_NAME = "knowledge_search"
DEFAULT_KNOWLEDGE_SEARCH_TOP_K = 5
DEFAULT_CONTENT_MAX_CHARS = 800


def get_document_by_id(doc_id):
    from python_rag.app.modules.documents.repo import get_document_by_id as repo_get_document_by_id

    return repo_get_document_by_id(doc_id)


def search_in_documents(**kwargs):
    from python_rag.app.modules.retrieval.service import (
        search_in_documents as retrieval_search_in_documents,
    )

    return retrieval_search_in_documents(**kwargs)


def _truncate_content(content: Any, max_chars: int = DEFAULT_CONTENT_MAX_CHARS) -> str:
    text = str(content or "").strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"


def _safe_score(value: Any) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def _normalize_top_k(value: Any) -> int:
    if value is None or value == "":
        return DEFAULT_KNOWLEDGE_SEARCH_TOP_K
    try:
        top_k = int(value)
    except (TypeError, ValueError):
        return DEFAULT_KNOWLEDGE_SEARCH_TOP_K
    return min(20, max(1, top_k))


class KnowledgeSearchTool(BaseTool):
    name = KNOWLEDGE_SEARCH_TOOL_NAME
    description = "Search the ready knowledge base and return the most relevant chunks."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "User question or rewritten retrieval query.",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of chunks to return.",
                "default": DEFAULT_KNOWLEDGE_SEARCH_TOP_K,
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    timeout_ms = 30000
    permission_level = "readonly"

    def __init__(
        self,
        max_content_chars: int = DEFAULT_CONTENT_MAX_CHARS,
        **kwargs,
    ):
        self.max_content_chars = max_content_chars
        super().__init__(**kwargs)

    def _get_title(self, doc_id: Optional[int], title_cache: Dict[int, str]) -> str:
        if doc_id is None:
            return ""
        if doc_id in title_cache:
            return title_cache[doc_id]

        title = ""
        try:
            document = get_document_by_id(doc_id)
            title = (document or {}).get("filename") or ""
        except Exception:
            title = ""

        title_cache[doc_id] = title
        return title

    def _format_hit(self, hit: Dict[str, Any], title_cache: Dict[int, str]) -> Dict[str, Any]:
        doc_id = hit.get("doc_id")
        try:
            document_id = int(doc_id) if doc_id is not None else None
        except (TypeError, ValueError):
            document_id = None

        return {
            "chunk_id": hit.get("chunk_id"),
            "chunk_index": hit.get("chunk_index"),
            "doc_id": document_id,
            "document_id": document_id,
            "title": self._get_title(document_id, title_cache),
            "content": _truncate_content(
                hit.get("content") or hit.get("snippet") or "",
                self.max_content_chars,
            ),
            "snippet": hit.get("snippet") or "",
            "score": _safe_score(hit.get("score")),
        }

    async def run(self, arguments: dict) -> dict:
        arguments = arguments or {}
        query = str(arguments.get("query") or "").strip()
        top_k = _normalize_top_k(arguments.get("top_k"))

        if not query:
            return {
                "results": [],
                "total": 0,
                "error": "query is required",
            }

        try:
            search_result = search_in_documents(
                query=query,
                top_k=top_k,
                track_metric=True,
            )
            hits = search_result.get("hits") or []
            title_cache: Dict[int, str] = {}
            results = [
                self._format_hit(hit, title_cache)
                for hit in hits[:top_k]
            ]
            return {
                "results": results,
                "total": len(results),
            }
        except Exception as exc:
            return {
                "results": [],
                "total": 0,
                "error": str(exc),
            }


def register_knowledge_tools(registry: ToolRegistry = default_registry) -> ToolRegistry:
    registry.register(KnowledgeSearchTool(), overwrite=True)
    return registry


register_knowledge_tools()


__all__ = [
    "DEFAULT_CONTENT_MAX_CHARS",
    "DEFAULT_KNOWLEDGE_SEARCH_TOP_K",
    "KNOWLEDGE_SEARCH_TOOL_NAME",
    "KnowledgeSearchTool",
    "register_knowledge_tools",
]
