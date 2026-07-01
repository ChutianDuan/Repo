import asyncio

from python_rag.app.agent.orchestrator import AgentOrchestrator
from python_rag.app.agent.tools import LIST_MESSAGE_CITATIONS_TOOL_NAME, default_registry
from python_rag.app.agent.tools.local.citation_tools import ListMessageCitationsTool
from python_rag.app.agent.tools.local.document_tools import (
    DOCUMENT_DETAIL_TOOL_NAME,
    LIST_READY_DOCUMENTS_TOOL_NAME,
    GetDocumentDetailTool,
    ListReadyDocumentsTool,
)
from python_rag.app.agent.tools.local.knowledge_tools import (
    KNOWLEDGE_SEARCH_TOOL_NAME,
    KnowledgeSearchTool,
)
from python_rag.app.agent.tools.registry import ToolRegistry


def test_list_message_citations_tool_returns_saved_citations(monkeypatch):
    calls = []

    def fake_list_citations_by_message_ids(message_ids):
        calls.append(message_ids)
        return {
            10: [
                {
                    "citation_id": 1,
                    "doc_id": "7",
                    "chunk_id": 21,
                    "chunk_index": 3,
                    "score": "0.8912349",
                    "snippet": "important citation",
                    "created_at": "2026-01-02T03:04:05",
                }
            ]
        }

    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.citation_tools.list_citations_by_message_ids",
        fake_list_citations_by_message_ids,
    )

    result = asyncio.run(ListMessageCitationsTool().run({"message_id": "10"}))

    assert calls == [[10]]
    assert result == {
        "ok": True,
        "error": None,
        "data": {
            "message_id": 10,
            "citations": [
                {
                    "citation_id": 1,
                    "doc_id": 7,
                    "document_id": 7,
                    "chunk_id": 21,
                    "chunk_index": 3,
                    "score": 0.891235,
                    "snippet": "important citation",
                    "created_at": "2026-01-02T03:04:05",
                }
            ],
            "total": 1,
        },
    }


def test_list_message_citations_tool_truncates_snippet(monkeypatch):
    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.citation_tools.list_citations_by_message_ids",
        lambda message_ids: {
            10: [
                {
                    "citation_id": 1,
                    "doc_id": 7,
                    "chunk_id": 21,
                    "chunk_index": 3,
                    "score": 1,
                    "snippet": "abcdefghijklmnopqrstuvwxyz",
                    "created_at": None,
                }
            ]
        },
    )

    result = asyncio.run(
        ListMessageCitationsTool(max_snippet_chars=10).run({"message_id": 10})
    )

    assert result["data"]["citations"][0]["snippet"] == "abcdefghij\n...[truncated]"


def test_list_message_citations_tool_returns_error_for_invalid_message_id():
    result = asyncio.run(ListMessageCitationsTool().run({"message_id": 0}))

    assert result == {
        "ok": False,
        "error": "message_id is required",
        "data": {
            "citations": [],
            "total": 0,
        },
    }


def test_list_message_citations_tool_returns_error_on_failure(monkeypatch):
    def fake_list_citations_by_message_ids(message_ids):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.citation_tools.list_citations_by_message_ids",
        fake_list_citations_by_message_ids,
    )

    result = asyncio.run(ListMessageCitationsTool().run({"message_id": 10}))

    assert result == {
        "ok": False,
        "error": "database unavailable",
        "data": {
            "message_id": 10,
            "citations": [],
            "total": 0,
        },
    }


def test_list_message_citations_tool_is_registered_and_exports_schema():
    assert default_registry.has(LIST_MESSAGE_CITATIONS_TOOL_NAME)

    schema = default_registry.export_openai_tools_schema(
        names=[LIST_MESSAGE_CITATIONS_TOOL_NAME],
        include_runtime_fields=True,
    )

    assert schema[0]["type"] == "function"
    assert schema[0]["function"]["name"] == LIST_MESSAGE_CITATIONS_TOOL_NAME
    assert schema[0]["function"]["parameters"]["required"] == ["message_id"]
    assert schema[0]["x_timeout_ms"] == 10000
    assert schema[0]["x_permission_level"] == "readonly"


def test_agent_orchestrator_exposes_citation_tool_schema():
    registry = ToolRegistry([
        KnowledgeSearchTool(),
        GetDocumentDetailTool(),
        ListReadyDocumentsTool(),
        ListMessageCitationsTool(),
    ])

    schema = AgentOrchestrator(registry=registry)._tool_schemas()

    assert [tool["function"]["name"] for tool in schema] == [
        KNOWLEDGE_SEARCH_TOOL_NAME,
        DOCUMENT_DETAIL_TOOL_NAME,
        LIST_READY_DOCUMENTS_TOOL_NAME,
        LIST_MESSAGE_CITATIONS_TOOL_NAME,
    ]
