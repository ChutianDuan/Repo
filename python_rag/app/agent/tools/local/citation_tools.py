from typing import Any, Dict, List, Optional

from python_rag.app.agent.tools.base import BaseTool
from python_rag.app.agent.tools.registry import ToolRegistry, default_registry


LIST_MESSAGE_CITATIONS_TOOL_NAME = "list_message_citations"
DEFAULT_CITATION_SNIPPET_MAX_CHARS = 600


def list_citations_by_message_ids(message_ids):
    from python_rag.app.modules.chat.repo import (
        list_citations_by_message_ids as repo_list_citations_by_message_ids,
    )

    return repo_list_citations_by_message_ids(message_ids)


def _normalize_message_id(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        message_id = int(value)
    except (TypeError, ValueError):
        return None
    if message_id <= 0:
        return None
    return message_id


def _safe_score(value: Any) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def _truncate_snippet(value: Any, max_chars: int) -> str:
    snippet = str(value or "").strip()
    if max_chars <= 0 or len(snippet) <= max_chars:
        return snippet
    return snippet[:max_chars].rstrip() + "\n...[truncated]"


def _format_citation(row: Dict[str, Any], max_snippet_chars: int) -> Dict[str, Any]:
    doc_id = row.get("doc_id")
    try:
        document_id = int(doc_id) if doc_id is not None else None
    except (TypeError, ValueError):
        document_id = None

    return {
        "citation_id": row.get("citation_id"),
        "doc_id": document_id,
        "document_id": document_id,
        "chunk_id": row.get("chunk_id"),
        "chunk_index": row.get("chunk_index"),
        "score": _safe_score(row.get("score")),
        "snippet": _truncate_snippet(row.get("snippet"), max_snippet_chars),
        "created_at": row.get("created_at"),
    }


class ListMessageCitationsTool(BaseTool):
    name = LIST_MESSAGE_CITATIONS_TOOL_NAME
    description = "List saved citations for an assistant message by message_id."
    input_schema = {
        "type": "object",
        "properties": {
            "message_id": {
                "type": "integer",
                "description": "Assistant message id whose saved citations should be listed.",
                "minimum": 1,
            },
        },
        "required": ["message_id"],
        "additionalProperties": False,
    }
    timeout_ms = 10000
    permission_level = "readonly"

    def __init__(
        self,
        max_snippet_chars: int = DEFAULT_CITATION_SNIPPET_MAX_CHARS,
        **kwargs,
    ):
        self.max_snippet_chars = max_snippet_chars
        super().__init__(**kwargs)

    async def run(self, arguments: dict) -> dict:
        arguments = arguments or {}
        message_id = _normalize_message_id(arguments.get("message_id"))
        if message_id is None:
            return {
                "citations": [],
                "total": 0,
                "error": "message_id is required",
            }

        try:
            citations_map = list_citations_by_message_ids([message_id])
            rows: List[Dict[str, Any]] = citations_map.get(message_id, [])
            citations = [
                _format_citation(row, self.max_snippet_chars)
                for row in rows
            ]
            return {
                "message_id": message_id,
                "citations": citations,
                "total": len(citations),
            }
        except Exception as exc:
            return {
                "message_id": message_id,
                "citations": [],
                "total": 0,
                "error": str(exc),
            }


def register_citation_tools(registry: ToolRegistry = default_registry) -> ToolRegistry:
    registry.register(ListMessageCitationsTool(), overwrite=True)
    return registry


register_citation_tools()


__all__ = [
    "DEFAULT_CITATION_SNIPPET_MAX_CHARS",
    "LIST_MESSAGE_CITATIONS_TOOL_NAME",
    "ListMessageCitationsTool",
    "register_citation_tools",
]
