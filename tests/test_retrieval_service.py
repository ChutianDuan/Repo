import json
import time
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile

try:
    import faiss
    import numpy as np
except ModuleNotFoundError as exc:
    if "pytest" in sys.modules:
        import pytest

        pytest.skip(
            "retrieval comparison tests require numpy and faiss",
            allow_module_level=True,
        )
    raise RuntimeError("retrieval comparison requires numpy and faiss") from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from python_rag.modules.ingest.chunking_service import (
    chunk_text_by_title,
    extract_text_from_document,
)
from python_rag.modules.ingest.embedding_service import (
    embed_documents,
    get_embedding_model_name,
    get_embedding_provider,
)
from python_rag.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from python_rag.modules.monitor.request_metrics import (
    build_usage_metrics,
    estimate_messages_tokens,
    estimate_text_tokens,
)
from python_rag.modules.retrieval import reranker_service
from python_rag.modules.retrieval import service as retrieval_service
from python_rag.utils import http_client


DOC_ID = 1


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
            "index_path": "doc_{0}".format(doc_id),
            "mapping_path": "mapping_{0}".format(doc_id),
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
                "content": "faiss doc {0}".format(doc_id),
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
                "content": "bm25 doc {0}".format(doc_id),
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


def _build_chunks(document_path, *, chunk_size, overlap):
    document_path = Path(document_path)
    if not document_path.exists():
        raise FileNotFoundError("document path does not exist: {0}".format(document_path))

    text = extract_text_from_document(str(document_path), document_path.name)
    chunks = chunk_text_by_title(
        text,
        filename=document_path.name,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    if not chunks:
        raise RuntimeError("chunk result is empty: {0}".format(document_path))
    return text, chunks


def _build_temp_index(chunks, embeddings):
    vectors = np.asarray(embeddings, dtype="float32")
    if vectors.ndim != 2:
        raise ValueError("document embeddings must be a 2D matrix")

    index_dir = Path(tempfile.mkdtemp(prefix="retrieval_compare_"))
    index_path = index_dir / "doc_{0}.faiss".format(DOC_ID)
    mapping_path = index_dir / "doc_{0}_mapping.json".format(DOC_ID)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(index_path))

    mapping = []
    for chunk_index, chunk in enumerate(chunks):
        mapping.append(
            {
                "row_id": chunk_index,
                "chunk_id": chunk_index + 1,
                "doc_id": DOC_ID,
                "chunk_index": chunk_index,
                "content": chunk,
            }
        )

    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    return {
        "doc_id": DOC_ID,
        "status": "READY",
        "embedding_model": get_embedding_model_name(),
        "index_path": str(index_path),
        "mapping_path": str(mapping_path),
        "chunk_count": len(chunks),
    }


@contextmanager
def _patched_retrieval_runtime(
    index_meta,
    *,
    recall_provider,
    rerank_enable,
    context_window,
    context_max_chars,
):
    old_retrieval_values = {
        "RETRIEVAL_RECALL_PROVIDER": retrieval_service.RETRIEVAL_RECALL_PROVIDER,
        "RERANK_ENABLE": retrieval_service.RERANK_ENABLE,
        "RETRIEVAL_CONTEXT_WINDOW": retrieval_service.RETRIEVAL_CONTEXT_WINDOW,
        "RETRIEVAL_CONTEXT_MAX_CHARS": retrieval_service.RETRIEVAL_CONTEXT_MAX_CHARS,
        "get_document_index_by_doc_id": retrieval_service.get_document_index_by_doc_id,
        "list_ready_document_ids": retrieval_service.list_ready_document_ids,
        "record_request_metric": retrieval_service.record_request_metric,
    }
    old_reranker_values = {
        "RERANK_ENABLE": reranker_service.RERANK_ENABLE,
        "RERANK_PROVIDER": reranker_service.RERANK_PROVIDER,
        "RERANK_FALLBACK_TO_FAISS": reranker_service.RERANK_FALLBACK_TO_FAISS,
    }

    retrieval_service.RETRIEVAL_RECALL_PROVIDER = recall_provider
    retrieval_service.RERANK_ENABLE = rerank_enable
    retrieval_service.RETRIEVAL_CONTEXT_WINDOW = context_window
    retrieval_service.RETRIEVAL_CONTEXT_MAX_CHARS = context_max_chars
    retrieval_service.get_document_index_by_doc_id = lambda doc_id: index_meta
    retrieval_service.list_ready_document_ids = lambda **kwargs: [DOC_ID]
    retrieval_service.record_request_metric = lambda **kwargs: None

    reranker_service.RERANK_ENABLE = rerank_enable
    reranker_service.RERANK_PROVIDER = "cross_encoder"
    reranker_service.RERANK_FALLBACK_TO_FAISS = True

    try:
        yield
    finally:
        for name, value in old_retrieval_values.items():
            setattr(retrieval_service, name, value)
        for name, value in old_reranker_values.items():
            setattr(reranker_service, name, value)


def _run_case(
    label,
    query,
    index_meta,
    *,
    recall_provider,
    rerank_enable,
    context_window,
    context_max_chars,
    top_k,
    candidate_top_k,
):
    with _patched_retrieval_runtime(
        index_meta,
        recall_provider=recall_provider,
        rerank_enable=rerank_enable,
        context_window=context_window,
        context_max_chars=context_max_chars,
    ):
        result = retrieval_service.search_in_document(
            doc_id=DOC_ID,
            query=query,
            top_k=top_k,
            candidate_top_k=candidate_top_k,
            track_metric=False,
        )

    result["label"] = label
    return result


def run_retrieval_comparison(
    document_path,
    query,
    *,
    chunk_size=800,
    overlap=100,
    top_k=3,
    candidate_top_k=30,
    context_window=1,
    context_max_chars=3000,
):
    """
    对比三条 retrieval 链路：
    1. embedding only：chunk -> embedding -> FAISS
    2. hybrid rerank：chunk -> embedding -> FAISS + BM25 -> RRF -> cross-encoder
    3. hybrid rerank expanded：第 2 条链路 + 命中 chunk 的前后文扩展
    """
    document_path = Path(document_path)
    text, chunks = _build_chunks(
        document_path,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    embeddings = embed_documents(chunks)
    index_meta = _build_temp_index(chunks, embeddings)

    cases = [
        {
            "label": "embedding_only",
            "recall_provider": "faiss",
            "rerank_enable": False,
            "context_window": 0,
        },
        {
            "label": "embedding_bm25_cross_encoder",
            "recall_provider": "hybrid_rrf",
            "rerank_enable": True,
            "context_window": 0,
        },
        {
            "label": "embedding_bm25_cross_encoder_expanded",
            "recall_provider": "hybrid_rrf",
            "rerank_enable": True,
            "context_window": context_window,
        },
    ]

    results = []
    for case in cases:
        results.append(
            _run_case(
                case["label"],
                query,
                index_meta,
                recall_provider=case["recall_provider"],
                rerank_enable=case["rerank_enable"],
                context_window=case["context_window"],
                context_max_chars=context_max_chars,
                top_k=top_k,
                candidate_top_k=candidate_top_k,
            )
        )

    return {
        "path": str(document_path),
        "filename": document_path.name,
        "query": query,
        "embedding_provider": get_embedding_provider(),
        "embedding_model": get_embedding_model_name(),
        "text_chars": len(text),
        "chunk_count": len(chunks),
        "embedding_shape": tuple(np.asarray(embeddings).shape),
        "index_path": index_meta["index_path"],
        "mapping_path": index_meta["mapping_path"],
        "results": results,
    }


def _hit_preview(hit, max_chars=500):
    content = hit.get("content") or ""
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rstrip() + "\n...[truncated]"


def _chunks_for_llm(result):
    chunks = []
    for rank, hit in enumerate(result["hits"], start=1):
        chunks.append(
            {
                "rank": rank,
                "chunk_index": hit.get("chunk_index"),
                "score": hit.get("score"),
                "faiss_score": hit.get("faiss_score"),
                "bm25_score": hit.get("bm25_score"),
                "rrf_score": hit.get("rrf_score"),
                "rerank_score": hit.get("rerank_score"),
                "context_window": hit.get("context_window"),
                "content": hit.get("content") or "",
            }
        )
    return chunks


def _build_rag_messages(query, result):
    return [
        {
            "role": "system",
            "content": (
                "你是一个 RAG 问答助手。只能根据用户提供的 chunks 回答问题。"
                "如果 chunks 中没有足够信息，请直接说明不知道。"
                "回答要简洁、准确，不要评价召回策略。"
            ),
        },
        {
            "role": "user",
            "content": (
                "召回策略：{0}\n\n"
                "chunks:\n{1}\n\n"
                "问题：{2}\n\n"
                "请基于以上 chunks 回答问题。"
            ).format(
                result["label"],
                json.dumps(_chunks_for_llm(result), ensure_ascii=False, indent=2),
                query,
            ),
        },
    ]


def _iter_sse_data(response):
    event_lines = []
    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue

        line = raw_line.rstrip("\r")
        if line == "":
            data = _flush_sse_data(event_lines)
            event_lines = []
            if data is not None:
                yield data
            continue

        if line.startswith(":"):
            continue
        event_lines.append(line)

    data = _flush_sse_data(event_lines)
    if data is not None:
        yield data


def _flush_sse_data(event_lines):
    data_lines = []
    for line in event_lines:
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return None
    return "\n".join(data_lines)


def _extract_stream_delta(chunk_json):
    choices = chunk_json.get("choices") or []
    if not choices:
        return ""

    first = choices[0] or {}
    delta = first.get("delta")
    if isinstance(delta, dict) and delta.get("content") is not None:
        return str(delta.get("content") or "")
    if first.get("text") is not None:
        return str(first.get("text") or "")
    return ""


def _ask_vllm_with_result(url, headers, query, result, *, model, max_tokens):
    messages = _build_rag_messages(query, result)
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    started_at = time.perf_counter()
    response = http_client.post(
        url,
        headers=headers,
        json=payload,
        timeout=120,
        stream=True,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            "vLLM chat completion failed case={0} status={1} body={2}".format(
                result["label"],
                response.status_code,
                response.text[:2000],
            )
        )

    answer_parts = []
    usage = None
    response_model = payload["model"]
    finish_reason = None
    ttft_ms = None

    for data_text in _iter_sse_data(response):
        if data_text == "[DONE]":
            break

        chunk_json = json.loads(data_text)
        if chunk_json.get("model"):
            response_model = chunk_json["model"]
        if chunk_json.get("usage") is not None:
            usage = chunk_json.get("usage")

        choices = chunk_json.get("choices") or []
        if choices:
            finish_reason = choices[0].get("finish_reason")

        delta_text = _extract_stream_delta(chunk_json)
        if not delta_text:
            continue
        if ttft_ms is None:
            ttft_ms = int((time.perf_counter() - started_at) * 1000)
        answer_parts.append(delta_text)

    answer = "".join(answer_parts)
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    usage_metrics = build_usage_metrics(
        usage,
        messages=messages,
        answer_text=answer,
    )
    return {
        "case": result["label"],
        "model": response_model,
        "prompt_tokens_est": estimate_messages_tokens(messages),
        "completion_tokens_est": estimate_text_tokens(answer),
        "answer_total_tokens": usage_metrics["total_tokens"],
        "ttft_ms": ttft_ms,
        "latency_ms": latency_ms,
        "finish_reason": finish_reason,
        "usage": usage_metrics,
        "answer": answer,
    }


def compare_retrieval_answers_with_vllm(
    comparison,
    *,
    base_url=None,
    api_key=None,
    model=None,
    max_tokens=512,
):
    base_url = (base_url or LLM_BASE_URL or "").rstrip("/")
    if not base_url:
        raise RuntimeError("LLM_BASE_URL is not configured")

    url = base_url + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    api_key = LLM_API_KEY if api_key is None else api_key
    if api_key:
        headers["Authorization"] = "Bearer {0}".format(api_key)

    selected_model = model or LLM_MODEL or "local-llm"
    answers = []
    for result in comparison["results"]:
        answers.append(
            _ask_vllm_with_result(
                url,
                headers,
                comparison["query"],
                result,
                model=selected_model,
                max_tokens=max_tokens,
            )
        )
    return answers


def print_retrieval_comparison_result(comparison):
    print("=" * 100)
    print("path:", comparison["path"])
    print("filename:", comparison["filename"])
    print("query:", comparison["query"])
    print("embedding_provider:", comparison["embedding_provider"])
    print("embedding_model:", comparison["embedding_model"])
    print("text_chars:", comparison["text_chars"])
    print("chunk_count:", comparison["chunk_count"])
    print("embedding_shape:", comparison["embedding_shape"])
    print("index_path:", comparison["index_path"])
    print("mapping_path:", comparison["mapping_path"])

    for result in comparison["results"]:
        metrics = result["metrics"]
        print("=" * 100)
        print("case:", result["label"])
        print("recall_provider:", metrics["recall_provider"])
        print("candidate_count:", metrics["candidate_count"])
        print("faiss_candidate_count:", metrics["faiss_candidate_count"])
        print("bm25_candidate_count:", metrics["bm25_candidate_count"])
        print("rerank:", metrics["rerank"])
        print("context_expansion:", metrics["context_expansion"])

        for hit in result["hits"]:
            print("-" * 80)
            print("rank:", hit.get("rank"))
            print("chunk_index:", hit.get("chunk_index"))
            print("score:", hit.get("score"))
            print("faiss_score:", hit.get("faiss_score"))
            print("bm25_score:", hit.get("bm25_score"))
            print("rrf_score:", hit.get("rrf_score"))
            print("rerank_score:", hit.get("rerank_score"))
            print("context_window:", hit.get("context_window"))
            print(_hit_preview(hit))
        print("-" * 80)


def print_vllm_answer_comparison(answers):
    print("=" * 100)
    print("vllm_answers:")
    for answer_result in answers:
        print("-" * 80)
        print("case:", answer_result["case"])
        print("model:", answer_result["model"])
        print("prompt_tokens_est:", answer_result["prompt_tokens_est"])
        print("completion_tokens_est:", answer_result["completion_tokens_est"])
        print("answer_total_tokens:", answer_result["answer_total_tokens"])
        print("ttft_ms:", answer_result["ttft_ms"])
        print("latency_ms:", answer_result["latency_ms"])
        print("finish_reason:", answer_result["finish_reason"])
        print("usage:", answer_result["usage"])
        print("answer:")
        print(answer_result["answer"])



if __name__ == "__main__":
    comparison = run_retrieval_comparison(
        document_path="tests/data/merged.md",
        query="智能指针所有权",
        chunk_size=800,
        overlap=100,
        top_k=3,
        candidate_top_k=30,
        context_window=1,
        context_max_chars=3000,
    )
    print_retrieval_comparison_result(comparison)
    answers = compare_retrieval_answers_with_vllm(comparison)
    print_vllm_answer_comparison(answers)
