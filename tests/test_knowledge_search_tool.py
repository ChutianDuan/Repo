import asyncio

from python_rag.app.agent.tools import KNOWLEDGE_SEARCH_TOOL_NAME, default_registry
from python_rag.app.agent.tools.local.knowledge_tools import KnowledgeSearchTool


def test_knowledge_search_tool_returns_retrieval_results(monkeypatch):
    calls = []

    def fake_search_in_documents(query, top_k, track_metric=True):
        calls.append(
            {
                "query": query,
                "top_k": top_k,
                "track_metric": track_metric,
            }
        )
        return {
            "hits": [
                {
                    "chunk_id": 1,
                    "chunk_index": 0,
                    "doc_id": 7,
                    "content": "important context",
                    "snippet": "important context",
                    "score": 0.8912349,
                },
                {
                    "chunk_id": 2,
                    "chunk_index": 1,
                    "doc_id": 7,
                    "content": "more context",
                    "snippet": "more context",
                    "score": 0.5,
                },
            ]
        }

    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.knowledge_tools.search_in_documents",
        fake_search_in_documents,
    )
    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.knowledge_tools.get_document_by_id",
        lambda doc_id: {"id": doc_id, "filename": "guide.md"},
    )

    result = asyncio.run(
        KnowledgeSearchTool().run(
            {
                "query": "how does retrieval work?",
                "top_k": 2,
            }
        )
    )

    assert calls == [
        {
            "query": "how does retrieval work?",
            "top_k": 2,
            "track_metric": True,
        }
    ]
    assert result == {
        "results": [
            {
                "chunk_id": 1,
                "chunk_index": 0,
                "doc_id": 7,
                "document_id": 7,
                "title": "guide.md",
                "content": "important context",
                "snippet": "important context",
                "score": 0.891235,
            },
            {
                "chunk_id": 2,
                "chunk_index": 1,
                "doc_id": 7,
                "document_id": 7,
                "title": "guide.md",
                "content": "more context",
                "snippet": "more context",
                "score": 0.5,
            },
        ],
        "total": 2,
    }


def test_knowledge_search_tool_truncates_content(monkeypatch):
    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.knowledge_tools.search_in_documents",
        lambda **kwargs: {
            "hits": [
                {
                    "chunk_id": 1,
                    "chunk_index": 0,
                    "doc_id": 7,
                    "content": "abcdefghijklmnopqrstuvwxyz",
                    "score": 1,
                }
            ]
        },
    )
    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.knowledge_tools.get_document_by_id",
        lambda doc_id: {"id": doc_id, "filename": "long.md"},
    )

    result = asyncio.run(
        KnowledgeSearchTool(max_content_chars=10).run(
            {
                "query": "alphabet",
                "top_k": 1,
            }
        )
    )

    assert result["total"] == 1
    assert result["results"][0]["content"] == "abcdefghij\n...[truncated]"


def test_knowledge_search_tool_returns_error_on_failure(monkeypatch):
    def fake_search_in_documents(**kwargs):
        raise RuntimeError("retrieval backend unavailable")

    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.knowledge_tools.search_in_documents",
        fake_search_in_documents,
    )

    result = asyncio.run(
        KnowledgeSearchTool().run(
            {
                "query": "hello",
                "top_k": 5,
            }
        )
    )

    assert result == {
        "results": [],
        "total": 0,
        "error": "retrieval backend unavailable",
    }


def test_knowledge_search_tool_returns_error_for_empty_query():
    result = asyncio.run(KnowledgeSearchTool().run({"query": "   "}))

    assert result == {
        "results": [],
        "total": 0,
        "error": "query is required",
    }


def test_knowledge_search_tool_is_registered_and_exports_schema():
    assert default_registry.has(KNOWLEDGE_SEARCH_TOOL_NAME)

    schema = default_registry.export_openai_tools_schema(
        names=[KNOWLEDGE_SEARCH_TOOL_NAME],
        include_runtime_fields=True,
    )

    assert schema[0]["type"] == "function"
    assert schema[0]["function"]["name"] == KNOWLEDGE_SEARCH_TOOL_NAME
    assert schema[0]["function"]["parameters"]["required"] == ["query"]
    assert schema[0]["x_timeout_ms"] == 30000
    assert schema[0]["x_permission_level"] == "readonly"
