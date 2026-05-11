import pytest

from python_rag.modules.retrieval import reranker_service


def test_rerank_falls_back_to_recall_order(monkeypatch):
    monkeypatch.setattr(reranker_service, "RERANK_ENABLE", True)
    monkeypatch.setattr(reranker_service, "RERANK_PROVIDER", "cross_encoder")
    monkeypatch.setattr(reranker_service, "RERANK_FALLBACK_TO_FAISS", True)

    def fail_score(query, hits):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(reranker_service, "_score_with_cross_encoder", fail_score)

    hits = [
        {"doc_id": 1, "chunk_id": 101, "chunk_index": 0, "score": 0.9, "content": "first"},
        {"doc_id": 1, "chunk_id": 102, "chunk_index": 1, "score": 0.8, "content": "second"},
    ]

    ranked, meta = reranker_service.rerank_hits(
        query="question",
        hits=hits,
        final_top_k=1,
        recall_provider="faiss",
    )

    assert [hit["chunk_id"] for hit in ranked] == [101]
    assert ranked[0]["rank"] == 1
    assert meta["fallback"] is True
    assert meta["returned_count"] == 1
    assert "model unavailable" in meta["error"]


def test_rerank_raises_when_fallback_disabled(monkeypatch):
    monkeypatch.setattr(reranker_service, "RERANK_ENABLE", True)
    monkeypatch.setattr(reranker_service, "RERANK_PROVIDER", "cross_encoder")
    monkeypatch.setattr(reranker_service, "RERANK_FALLBACK_TO_FAISS", False)
    monkeypatch.setattr(
        reranker_service,
        "_score_with_cross_encoder",
        lambda query, hits: (_ for _ in ()).throw(RuntimeError("model unavailable")),
    )

    with pytest.raises(RuntimeError, match="model unavailable"):
        reranker_service.rerank_hits(
            query="question",
            hits=[
                {
                    "doc_id": 1,
                    "chunk_id": 101,
                    "chunk_index": 0,
                    "score": 0.9,
                    "content": "first",
                }
            ],
            final_top_k=1,
        )
