import asyncio

from python_rag.app.agent.tools import KNOWLEDGE_SEARCH_TOOL_NAME, default_registry
from python_rag.app.agent.tools.local.knowledge_tools import (
    KnowledgeSearchTool,
    build_rewritten_queries,
)


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
            ],
            "metrics": {
                "recall_provider": "lancedb",
                "candidate_top_k": 50,
                "final_top_k": 2,
                "candidate_count": 12,
                "lancedb_candidate_count": 12,
                "mysql_hydrated_candidate_count": 10,
                "lancedb_ms": 7,
                "rerank_ms": 11,
                "retrieval_ms": 25,
                "rerank": {"used": True, "provider": "cross_encoder", "model": "reranker"},
            }
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

    assert calls[0] == {
        "query": "how does retrieval work?",
        "top_k": 2,
        "track_metric": True,
    }
    assert len(calls) > 1
    assert all(call["track_metric"] is (index == 0) for index, call in enumerate(calls))
    assert result["ok"] is True
    assert result["error"] is None
    data = result["data"]
    assert data["total"] == 2
    assert [item["chunk_id"] for item in data["results"]] == [1, 2]
    assert data["results"][0]["title"] == "guide.md"
    assert data["results"][0]["score"] == 0.891235
    assert data["results"][0]["lancedb_score"] == 0.0
    assert data["results"][0]["rerank_score"] == 0.0
    assert data["retrieval"]["provider"] == "lancedb"
    assert data["retrieval"]["vector_search_latency_ms"] == 7
    assert data["retrieval"]["rerank_latency_ms"] == 11
    assert data["retrieval"]["retrieval_latency_ms"] == 25
    assert data["retrieval"]["dense_top_k"] == 50
    assert data["retrieval"]["rerank_top_k"] == 2
    assert data["retrieval"]["query_rewrite"]["enabled"] is True
    assert data["retrieval"]["query_rewrite"]["queries"][0] == "how does retrieval work?"


def test_build_rewritten_queries_expands_domain_terms():
    queries = build_rewritten_queries("网页上传后怎么进行 embedding 检索？")

    assert queries[0] == "网页上传后怎么进行 embedding 检索？"
    assert len(queries) > 1
    assert any("URL HTML" in query for query in queries)
    assert any("embedding 向量" in query for query in queries)


def test_knowledge_search_tool_merges_multi_route_results(monkeypatch):
    calls = []

    def fake_search_in_documents(query, top_k, track_metric=True):
        calls.append(
            {
                "query": query,
                "top_k": top_k,
                "track_metric": track_metric,
            }
        )
        if "URL HTML" in query:
            return {
                "hits": [
                    {
                        "chunk_id": 20,
                        "chunk_index": 2,
                        "doc_id": 8,
                        "content": "web page extraction flow",
                        "snippet": "web page extraction flow",
                        "score": 0.92,
                    },
                ],
                "metrics": {"recall_provider": "lancedb"},
            }
        if "embedding 向量" in query:
            return {
                "hits": [
                    {
                        "chunk_id": 30,
                        "chunk_index": 3,
                        "doc_id": 8,
                        "content": "embedding index flow",
                        "snippet": "embedding index flow",
                        "score": 0.95,
                    },
                    {
                        "chunk_id": 10,
                        "chunk_index": 1,
                        "doc_id": 8,
                        "content": "original retrieval flow duplicate",
                        "snippet": "original retrieval flow duplicate",
                        "score": 0.7,
                    },
                ],
                "metrics": {"recall_provider": "lancedb"},
            }
        return {
            "hits": [
                {
                    "chunk_id": 10,
                    "chunk_index": 1,
                    "doc_id": 8,
                    "content": "original retrieval flow",
                    "snippet": "original retrieval flow",
                    "score": 0.6,
                },
            ],
            "metrics": {"recall_provider": "lancedb"},
        }

    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.knowledge_tools.search_in_documents",
        fake_search_in_documents,
    )
    monkeypatch.setattr(
        "python_rag.app.agent.tools.local.knowledge_tools.get_document_by_id",
        lambda doc_id: {"id": doc_id, "filename": "web.md"},
    )

    result = asyncio.run(
        KnowledgeSearchTool().run(
            {
                "query": "网页上传后怎么进行 embedding 检索？",
                "top_k": 3,
            }
        )
    )

    assert result["ok"] is True
    assert [item["chunk_id"] for item in result["data"]["results"]] == [30, 20, 10]
    assert len(calls) > 1
    assert calls[0]["track_metric"] is True
    assert all(call["track_metric"] is False for call in calls[1:])
    assert result["data"]["results"][0]["matched_queries"]
    assert result["data"]["retrieval"]["query_rewrite"]["successful_route_count"] == len(calls)


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

    assert result["ok"] is True
    assert result["data"]["total"] == 1
    assert result["data"]["results"][0]["content"] == "abcdefghij\n...[truncated]"


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
        "ok": False,
        "error": "retrieval backend unavailable",
        "data": {
            "results": [],
            "total": 0,
        },
    }


def test_knowledge_search_tool_returns_error_for_empty_query():
    result = asyncio.run(KnowledgeSearchTool().run({"query": "   "}))

    assert result == {
        "ok": False,
        "error": "query is required",
        "data": {
            "results": [],
            "total": 0,
        },
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
