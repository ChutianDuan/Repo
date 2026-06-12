from datetime import date, datetime
from typing import Any, Optional

from python_rag.app.agent.tools.base import BaseTool
from python_rag.app.agent.tools.registry import ToolRegistry, default_registry


DOCUMENT_DETAIL_TOOL_NAME = "get_document_detail"
LIST_READY_DOCUMENTS_TOOL_NAME = "list_ready_documents"
DEFAULT_LIST_READY_DOCUMENTS_LIMIT = 100
MAX_LIST_READY_DOCUMENTS_LIMIT = 1000


def get_document_by_id(doc_id):
    from python_rag.app.modules.documents.repo import get_document_by_id as repo_get_document_by_id

    return repo_get_document_by_id(doc_id)


def get_document_index_by_doc_id(doc_id):
    from python_rag.app.modules.documents.repo import (
        get_document_index_by_doc_id as repo_get_document_index_by_doc_id,
    )

    return repo_get_document_index_by_doc_id(doc_id)


def list_documents(status=None, limit=DEFAULT_LIST_READY_DOCUMENTS_LIMIT):
    from python_rag.app.modules.documents.repo import list_documents as repo_list_documents

    return repo_list_documents(status=status, limit=limit)


def _normalize_document_id(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        document_id = int(value)
    except (TypeError, ValueError):
        return None
    if document_id <= 0:
        return None
    return document_id


def _format_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _normalize_chunk_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _normalize_status(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_limit(value: Any) -> int:
    if value in (None, ""):
        return DEFAULT_LIST_READY_DOCUMENTS_LIMIT
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIST_READY_DOCUMENTS_LIMIT
    return min(MAX_LIST_READY_DOCUMENTS_LIMIT, max(1, limit))


def _is_ready_indexed_document(row: dict) -> bool:
    index_status = _normalize_status(row.get("index_status"))
    status = _normalize_status(row.get("status"))
    return index_status in ("indexed", "ready") and status not in ("failed", "failure")


def _format_document_item(row: dict) -> dict:
    return {
        "document_id": int(row.get("id")),
        "title": row.get("filename") or "",
        "status": _normalize_status(row.get("status")),
        "chunk_count": _normalize_chunk_count(row.get("chunk_count")),
        "created_at": _format_datetime(row.get("created_at")),
    }


class GetDocumentDetailTool(BaseTool):
    name = DOCUMENT_DETAIL_TOOL_NAME
    description = "Get document metadata by document_id."
    input_schema = {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "integer",
                "description": "Document id to look up.",
                "minimum": 1,
            },
        },
        "required": ["document_id"],
        "additionalProperties": False,
    }
    timeout_ms = 10000
    permission_level = "readonly"

    async def run(self, arguments: dict) -> dict:
        arguments = arguments or {}
        document_id = _normalize_document_id(arguments.get("document_id"))
        if document_id is None:
            return {
                "error": "document_id is required",
            }

        try:
            document = get_document_by_id(document_id)
            if not document:
                return {
                    "document_id": document_id,
                    "error": "document not found",
                }

            index = get_document_index_by_doc_id(document_id) or {}
            return {
                "document_id": int(document.get("id") or document_id),
                "title": document.get("filename") or "",
                "status": _normalize_status(document.get("status")),
                "chunk_count": _normalize_chunk_count(index.get("chunk_count")),
                "created_at": _format_datetime(document.get("created_at")),
            }
        except Exception as exc:
            return {
                "document_id": document_id,
                "error": str(exc),
            }


class ListReadyDocumentsTool(BaseTool):
    name = LIST_READY_DOCUMENTS_TOOL_NAME
    description = "List documents that are ready and indexed for knowledge retrieval."
    input_schema = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of ready documents to return.",
                "default": DEFAULT_LIST_READY_DOCUMENTS_LIMIT,
                "minimum": 1,
                "maximum": MAX_LIST_READY_DOCUMENTS_LIMIT,
            },
        },
        "additionalProperties": False,
    }
    timeout_ms = 10000
    permission_level = "readonly"

    async def run(self, arguments: dict) -> dict:
        arguments = arguments or {}
        limit = _normalize_limit(arguments.get("limit"))

        try:
            rows = list_documents(status="indexed", limit=limit)
            documents = [
                _format_document_item(row)
                for row in rows
                if _is_ready_indexed_document(row)
            ]
            return {
                "documents": documents,
                "total": len(documents),
            }
        except Exception as exc:
            return {
                "documents": [],
                "total": 0,
                "error": str(exc),
            }


def register_document_tools(registry: ToolRegistry = default_registry) -> ToolRegistry:
    registry.register(GetDocumentDetailTool(), overwrite=True)
    registry.register(ListReadyDocumentsTool(), overwrite=True)
    return registry


register_document_tools()


__all__ = [
    "DEFAULT_LIST_READY_DOCUMENTS_LIMIT",
    "DOCUMENT_DETAIL_TOOL_NAME",
    "GetDocumentDetailTool",
    "LIST_READY_DOCUMENTS_TOOL_NAME",
    "ListReadyDocumentsTool",
    "MAX_LIST_READY_DOCUMENTS_LIMIT",
    "register_document_tools",
]
