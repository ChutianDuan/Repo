import numpy as np

from python_rag.modules.retrieval import service as retrieval_service


def test_search_in_documents_hybrid_fanout_and_metrics(monkeypatch):
    monkeypatch.setattr(retrieval_service, "RETRIEVAL_RECALL_PROVIDER", "hybrid_rrf")
    monkeypatch.setattr(retrieval_service, "RERANK_ENABLE", True)
    monkeypatch.setattr(retrieval_service, "CHAT_CANDIDATE_TOP_K", 3)
    monkeypatch.setattr(retrieval_service, "get_embedding_model_name", lambda: "embedding-v1")
    monkeypatch.setattr(
        retrieval_service,
        "list_ready_document_ids",
        lambda user_id=None, embedding_model=None, limit=1000: [1, 2],
    )
    monkeypatch.setattr(
        retrieval_service,
        "get_document_index_by_doc_id",
        lambda doc_id: {
            "doc_id": doc_id,
            "status": "READY",
            "embedding_model": "embedding-v1",
            "index_path": f"doc_{doc_id}",
            "mapping_path": f"mapping_{doc_id}",
        },
    )
    monkeypatch.setattr(
        retrieval_service,
        "embed_query",
        lambda query: np.asarray([1.0, 0.0], dtype="float32"),
    )

    def fake_faiss(index_path, mapping_path, query_vector, top_k):
        doc_id = int(index_path.split("_")[-1])
        return [
            {
                "doc_id": doc_id,
                "chunk_id": doc_id * 100 + 1,
                "chunk_index": 0,
                "score": 0.9 - doc_id * 0.1,
                "content": f"faiss doc {doc_id}",
            }
        ]

    def fake_bm25(mapping_path, query, top_k):
        doc_id = int(mapping_path.split("_")[-1])
        return [
            {
                "doc_id": doc_id,
                "chunk_id": doc_id * 100 + 2,
                "chunk_index": 1,
                "bm25_score": 2.0 - doc_id * 0.1,
                "content": f"bm25 doc {doc_id}",
            }
        ]

    def fake_rerank(query, hits, final_top_k, recall_provider):
        ranked = []
        for rank, hit in enumerate(hits[:final_top_k], start=1):
            item = dict(hit)
            item["rank"] = rank
            ranked.append(item)
        return ranked, {"used": False, "fallback": True}

    monkeypatch.setattr(retrieval_service, "search_doc_faiss_index", fake_faiss)
    monkeypatch.setattr(retrieval_service, "search_doc_bm25_index", fake_bm25)
    monkeypatch.setattr(retrieval_service, "rerank_hits", fake_rerank)

    result = retrieval_service.search_in_documents(
        query="hello",
        top_k=2,
        track_metric=False,
    )

    assert result["doc_ids"] == [1, 2]
    assert result["doc_count"] == 2
    assert result["top_k"] == 2
    assert len(result["hits"]) == 2
    assert result["metrics"]["recall_provider"] == "hybrid_rrf"
    assert result["metrics"]["faiss_candidate_count"] == 2
    assert result["metrics"]["bm25_candidate_count"] == 2
    assert result["metrics"]["candidate_count"] == 4
