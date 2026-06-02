import asyncio
from datetime import datetime

from python_rag.app.agent.orchestrator import AgentOrchestrator
from python_rag.app.tools import LIST_READY_DOCUMENTS_TOOL_NAME, default_registry
from python_rag.app.tools.document_tools import (
    DOCUMENT_DETAIL_TOOL_NAME,
    GetDocumentDetailTool,
    ListReadyDocumentsTool,
)
from python_rag.app.tools.knowledge_tools import KNOWLEDGE_SEARCH_TOOL_NAME, KnowledgeSearchTool
from python_rag.app.tools.registry import ToolRegistry


def test_list_ready_documents_tool_returns_ready_indexed_documents(monkeypatch):
    calls = []

    def fake_list_documents(status=None, limit=100):
        calls.append({"status": status, "limit": limit})
        return [
            {
                "id": 1,
                "filename": "xxx.pdf",
                "status": "READY",
                "index_status": "READY",
                "chunk_count": "128",
                "created_at": datetime(2026, 1, 2, 3, 4, 5),
            },
            {
                "id": 2,
                "filename": "not-indexed.pdf",
                "status": "READY",
                "index_status": "BUILDING",
                "chunk_count": 9,
                "created_at": datetime(2026, 1, 3, 3, 4, 5),
            },
            {
                "id": 3,
                "filename": "failed.pdf",
                "status": "FAILED",
                "index_status": "READY",
                "chunk_count": 7,
                "created_at": datetime(2026, 1, 4, 3, 4, 5),
            },
        ]

    monkeypatch.setattr(
        "python_rag.app.tools.document_tools.list_documents",
        fake_list_documents,
    )

    result = asyncio.run(ListReadyDocumentsTool().run({"limit": "2"}))

    assert calls == [{"status": "READY", "limit": 2}]
    assert result == {
        "documents": [
            {
                "document_id": 1,
                "title": "xxx.pdf",
                "status": "ready",
                "chunk_count": 128,
                "created_at": "2026-01-02T03:04:05",
            }
        ],
        "total": 1,
    }


def test_list_ready_documents_tool_returns_empty_list(monkeypatch):
    monkeypatch.setattr(
        "python_rag.app.tools.document_tools.list_documents",
        lambda status=None, limit=100: [],
    )

    result = asyncio.run(ListReadyDocumentsTool().run({}))

    assert result == {"documents": [], "total": 0}


def test_list_ready_documents_tool_returns_error_on_failure(monkeypatch):
    def fake_list_documents(status=None, limit=100):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        "python_rag.app.tools.document_tools.list_documents",
        fake_list_documents,
    )

    result = asyncio.run(ListReadyDocumentsTool().run({}))

    assert result == {
        "documents": [],
        "total": 0,
        "error": "database unavailable",
    }


def test_list_ready_documents_tool_is_registered_and_exports_schema():
    assert default_registry.has(LIST_READY_DOCUMENTS_TOOL_NAME)

    schema = default_registry.export_openai_tools_schema(
        names=[LIST_READY_DOCUMENTS_TOOL_NAME],
        include_runtime_fields=True,
    )

    params = schema[0]["function"]["parameters"]
    assert schema[0]["type"] == "function"
    assert schema[0]["function"]["name"] == LIST_READY_DOCUMENTS_TOOL_NAME
    assert "required" not in params
    assert params["properties"]["limit"]["default"] == 100
    assert schema[0]["x_timeout_ms"] == 10000
    assert schema[0]["x_permission_level"] == "readonly"


def test_agent_orchestrator_exposes_list_ready_documents_tool_schema():
    registry = ToolRegistry([
        KnowledgeSearchTool(),
        GetDocumentDetailTool(),
        ListReadyDocumentsTool(),
    ])

    schema = AgentOrchestrator(registry=registry)._tool_schemas()

    assert [tool["function"]["name"] for tool in schema] == [
        KNOWLEDGE_SEARCH_TOOL_NAME,
        DOCUMENT_DETAIL_TOOL_NAME,
        LIST_READY_DOCUMENTS_TOOL_NAME,
    ]
