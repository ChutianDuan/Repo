import asyncio
from datetime import datetime

from python_rag.app.agent.orchestrator import AgentOrchestrator
from python_rag.app.agent.tools import DOCUMENT_DETAIL_TOOL_NAME, default_registry
from python_rag.app.agent.tools.local.document_tools import GetDocumentDetailTool
from python_rag.app.agent.tools.local.knowledge_tools import KNOWLEDGE_SEARCH_TOOL_NAME, KnowledgeSearchTool
from python_rag.app.agent.tools.registry import ToolRegistry


def test_get_document_detail_tool_returns_document_metadata(monkeypatch):
    calls = []

    def fake_get_document_by_id(doc_id):
        calls.append(("document", doc_id))
        return {
            "id": doc_id,
            "filename": "xxx.pdf",
            "status": "READY",
            "created_at": datetime(2026, 1, 2, 3, 4, 5),
        }

    def fake_get_document_index_by_doc_id(doc_id):
        calls.append(("index", doc_id))
        return {"doc_id": doc_id, "chunk_count": "128"}

    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.document_tools.get_document_by_id",
        fake_get_document_by_id,
    )
    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.document_tools.get_document_index_by_doc_id",
        fake_get_document_index_by_doc_id,
    )

    result = asyncio.run(GetDocumentDetailTool().run({"document_id": 1}))

    assert calls == [("document", 1), ("index", 1)]
    assert result == {
        "ok": True,
        "error": None,
        "data": {
            "document_id": 1,
            "title": "xxx.pdf",
            "status": "ready",
            "chunk_count": 128,
            "created_at": "2026-01-02T03:04:05",
        },
    }


def test_get_document_detail_tool_defaults_missing_index_chunk_count(monkeypatch):
    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.document_tools.get_document_by_id",
        lambda doc_id: {
            "id": doc_id,
            "filename": "draft.md",
            "status": "UPLOADED",
            "created_at": "2026-01-02T03:04:05",
        },
    )
    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.document_tools.get_document_index_by_doc_id",
        lambda doc_id: None,
    )

    result = asyncio.run(GetDocumentDetailTool().run({"document_id": "2"}))

    assert result == {
        "ok": True,
        "error": None,
        "data": {
            "document_id": 2,
            "title": "draft.md",
            "status": "uploaded",
            "chunk_count": 0,
            "created_at": "2026-01-02T03:04:05",
        },
    }


def test_get_document_detail_tool_returns_error_for_invalid_document_id():
    result = asyncio.run(GetDocumentDetailTool().run({"document_id": 0}))

    assert result == {
        "ok": False,
        "error": "document_id is required",
        "data": {},
    }


def test_get_document_detail_tool_returns_error_when_document_missing(monkeypatch):
    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.document_tools.get_document_by_id",
        lambda doc_id: None,
    )

    def fail_get_index(doc_id):
        raise AssertionError("index lookup should not run for a missing document")

    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.document_tools.get_document_index_by_doc_id",
        fail_get_index,
    )

    result = asyncio.run(GetDocumentDetailTool().run({"document_id": 404}))

    assert result == {
        "ok": False,
        "error": "document not found",
        "data": {
            "document_id": 404,
        },
    }


def test_get_document_detail_tool_is_registered_and_exports_schema():
    assert default_registry.has(DOCUMENT_DETAIL_TOOL_NAME)

    schema = default_registry.export_openai_tools_schema(
        names=[DOCUMENT_DETAIL_TOOL_NAME],
        include_runtime_fields=True,
    )

    assert schema[0]["type"] == "function"
    assert schema[0]["function"]["name"] == DOCUMENT_DETAIL_TOOL_NAME
    assert schema[0]["function"]["parameters"]["required"] == ["document_id"]
    assert schema[0]["x_timeout_ms"] == 10000
    assert schema[0]["x_permission_level"] == "readonly"


def test_agent_orchestrator_exposes_document_detail_tool_schema():
    registry = ToolRegistry([KnowledgeSearchTool(), GetDocumentDetailTool()])

    schema = AgentOrchestrator(registry=registry)._tool_schemas()

    assert [tool["function"]["name"] for tool in schema] == [
        KNOWLEDGE_SEARCH_TOOL_NAME,
        DOCUMENT_DETAIL_TOOL_NAME,
    ]
