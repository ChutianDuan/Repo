import pytest

from python_rag.app.modules.retrieval import reranker_service


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


def test_resolve_cross_encoder_model_path_downloads_on_cache_miss(monkeypatch):
    calls = []

    monkeypatch.setattr(reranker_service, "RERANK_LOCAL_FILES_ONLY", True)
    monkeypatch.setattr(reranker_service, "RERANK_DOWNLOAD_IF_MISSING", True)
    monkeypatch.setattr(reranker_service, "RERANK_CACHE_DIR", "/tmp/hf-cache")
    monkeypatch.setattr(reranker_service, "_is_local_model_path", lambda model_name: False)

    def fake_snapshot_download(
        model_name,
        *,
        cache_dir,
        local_files_only,
        force_download=False,
    ):
        calls.append((model_name, cache_dir, local_files_only, force_download))
        if local_files_only:
            raise RuntimeError("cache miss")
        return "/tmp/hf-cache/snapshots/model"

    monkeypatch.setattr(reranker_service, "_snapshot_download", fake_snapshot_download)

    resolved = reranker_service._resolve_cross_encoder_model_path("BAAI/bge-reranker-base")

    assert resolved == "/tmp/hf-cache/snapshots/model"
    assert calls == [
        ("BAAI/bge-reranker-base", "/tmp/hf-cache", True, False),
        ("BAAI/bge-reranker-base", "/tmp/hf-cache", False, False),
    ]


def test_resolve_cross_encoder_model_path_redownloads_incomplete_snapshot(monkeypatch):
    calls = []

    monkeypatch.setattr(reranker_service, "RERANK_LOCAL_FILES_ONLY", True)
    monkeypatch.setattr(reranker_service, "RERANK_DOWNLOAD_IF_MISSING", True)
    monkeypatch.setattr(reranker_service, "RERANK_CACHE_DIR", "/tmp/hf-cache")
    monkeypatch.setattr(reranker_service, "_is_local_model_path", lambda model_name: False)

    def fake_snapshot_download(
        model_name,
        *,
        cache_dir,
        local_files_only,
        force_download=False,
    ):
        calls.append((local_files_only, force_download))
        return "/tmp/hf-cache/snapshots/model"

    def fake_has_model_weight_file(model_path):
        return len(calls) >= 2

    monkeypatch.setattr(reranker_service, "_snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(reranker_service, "_has_model_weight_file", fake_has_model_weight_file)

    resolved = reranker_service._resolve_cross_encoder_model_path("BAAI/bge-reranker-base")

    assert resolved == "/tmp/hf-cache/snapshots/model"
    assert calls == [(True, False), (False, True)]


def test_build_cross_encoder_kwargs_sanitizes_architectures(monkeypatch):
    monkeypatch.setattr(reranker_service, "RERANK_LOCAL_FILES_ONLY", True)
    monkeypatch.setattr(reranker_service, "RERANK_CACHE_DIR", None)

    kwargs = reranker_service._build_cross_encoder_kwargs(
        "/tmp/hf-cache/snapshots/model",
        "cuda",
    )

    assert kwargs["device"] == "cuda"
    assert kwargs["local_files_only"] is True
    assert kwargs["config_args"]["architectures"] == [
        "AutoModelForSequenceClassification"
    ]
