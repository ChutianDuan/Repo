import json
from pathlib import Path
import sys
import tempfile

import faiss
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from python_rag.modules.ingest.chunking_service import (
    chunk_text_by_title,
    extract_text_from_document,
)
from python_rag.modules.ingest.embedding_service import (
    embed_documents,
    embed_query,
    get_embedding_model_name,
    get_embedding_provider,
)
from python_rag.config import LLM_API_KEY, LLM_BASE_URL
from python_rag.modules.retrieval.bm25_service import search_doc_bm25_index
from python_rag.modules.retrieval.faiss_service import search_doc_faiss_index
from python_rag.modules.retrieval.fusion_service import fuse_hits_with_rrf
from python_rag.modules.retrieval.reranker_service import rerank_hits
from python_rag.modules.monitor.request_metrics import (
    build_usage_metrics,
    estimate_messages_tokens,
    estimate_text_tokens,
)
from python_rag.utils import http_client
from python_rag.utils.text_chunker import simple_chunk_text


RUN_LOCAL_RERANK = False


def _build_search_files(chunks, embeddings, strategy):
    embeddings = np.asarray(embeddings, dtype="float32")
    if embeddings.ndim != 2:
        raise ValueError("document embeddings must be a 2D matrix")

    index_dir = Path(tempfile.mkdtemp(prefix="chunking_recall_"))
    index_path = index_dir / "{0}.faiss".format(strategy)
    mapping_path = index_dir / "{0}_mapping.json".format(strategy)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, str(index_path))

    mapping = []
    for chunk_index, chunk in enumerate(chunks):
        mapping.append(
            {
                "row_id": chunk_index,
                "chunk_id": chunk_index + 1,
                "doc_id": 1,
                "chunk_index": chunk_index,
                "content": chunk,
            }
        )
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    return str(index_path), str(mapping_path)


def _recall_with_project_indexes(query, chunks, embeddings, strategy, top_k=3):
    index_path, mapping_path = _build_search_files(chunks, embeddings, strategy)
    candidate_top_k = top_k
    query_vector = embed_query(query)
    faiss_hits = search_doc_faiss_index(
        index_path=index_path,
        mapping_path=mapping_path,
        query_vector=query_vector,
        top_k=candidate_top_k,
    )
    bm25_hits = search_doc_bm25_index(
        mapping_path=mapping_path,
        query=query,
        top_k=candidate_top_k,
    )
    fused_hits = fuse_hits_with_rrf(
        [("bm25", bm25_hits), ("faiss", faiss_hits)],
        limit=candidate_top_k,
    )
    if RUN_LOCAL_RERANK:
        rerank_result, rerank_meta = rerank_hits(
            query=query,
            hits=fused_hits,
            final_top_k=top_k,
            recall_provider="hybrid_rrf",
        )
    else:
        rerank_result = fused_hits[:top_k]
        rerank_meta = {
            "enabled": False,
            "used": False,
            "provider": "disabled_in_script",
            "recall_provider": "hybrid_rrf",
            "candidate_count": len(fused_hits),
            "returned_count": len(rerank_result),
        }
    return {
        "index_path": index_path,
        "mapping_path": mapping_path,
        "faiss_hits": faiss_hits[:top_k],
        "bm25_hits": bm25_hits[:top_k],
        "fused_hits": fused_hits,
        "rerank_hits": rerank_result,
        "rerank_meta": rerank_meta,
    }


def _build_chunks(text, filename, strategy, chunk_size, overlap):
    if strategy == "title":
        return chunk_text_by_title(
            text,
            filename=filename,
            chunk_size=chunk_size,
            overlap=overlap,
        )
    if strategy == "simple":
        return simple_chunk_text(
            text,
            chunk_size=chunk_size,
            overlap=overlap,
        )
    raise ValueError("unsupported chunk strategy: {0}".format(strategy))


def run_document_embedding_recall(
    document_path,
    query,
    *,
    strategy="title",
    chunk_size=800,
    overlap=100,
    top_k=3,
):
    document_path = Path(document_path)
    if not document_path.exists():
        raise FileNotFoundError("document path does not exist: {0}".format(document_path))

    text = extract_text_from_document(str(document_path), document_path.name)
    chunks = _build_chunks(
        text,
        filename=document_path.name,
        strategy=strategy,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    embeddings = embed_documents(chunks)
    recall = _recall_with_project_indexes(
        query=query,
        chunks=chunks,
        embeddings=embeddings,
        strategy=strategy,
        top_k=top_k,
    )
    return {
        "path": str(document_path),
        "filename": document_path.name,
        "embedding_provider": get_embedding_provider(),
        "embedding_model": get_embedding_model_name(),
        "strategy": strategy,
        "text": text,
        "chunks": chunks,
        "embeddings": embeddings,
        "index_path": recall["index_path"],
        "mapping_path": recall["mapping_path"],
        "faiss_hits": recall["faiss_hits"],
        "bm25_hits": recall["bm25_hits"],
        "fused_hits": recall["fused_hits"],
        "rerank_hits": recall["rerank_hits"],
        "rerank_meta": recall["rerank_meta"],
    }


def print_document_embedding_recall_result(result, max_print_chunks=0):
    print("=" * 100)
    print("strategy:", result["strategy"])
    print("path:", result["path"])
    print("filename:", result["filename"])
    print("embedding_provider:", result["embedding_provider"])
    print("embedding_model:", result["embedding_model"])
    print("text_chars:", len(result["text"]))
    print("chunk_count:", len(result["chunks"]))
    print("embedding_shape:", result["embeddings"].shape)
    print("index_path:", result["index_path"])
    print("mapping_path:", result["mapping_path"])
    print()

    if max_print_chunks > 0:
        print("chunks:")
        chunks_to_print = result["chunks"][:max_print_chunks]
        for index, chunk in enumerate(chunks_to_print):
            print("-" * 80)
            print("chunk_index:", index)
            print("embedding_norm:", float(np.linalg.norm(result["embeddings"][index])))
            print(chunk)
        if len(result["chunks"]) > max_print_chunks:
            print("-" * 80)
            print(
                "chunk output truncated: showing {0} of {1}".format(
                    max_print_chunks,
                    len(result["chunks"]),
                )
            )
        print("-" * 80)
        print()

    print("faiss_hits:")
    for rank, hit in enumerate(result["faiss_hits"], start=1):
        print("-" * 80)
        print("rank:", rank)
        print("chunk_index:", hit["chunk_index"])
        print("score:", hit["score"])
        print(hit["content"])
    print("-" * 80)
    print()

    print("bm25_hits:")
    for rank, hit in enumerate(result["bm25_hits"], start=1):
        print("-" * 80)
        print("rank:", rank)
        print("chunk_index:", hit["chunk_index"])
        print("bm25_score:", hit["bm25_score"])
        print(hit["content"])
    print("-" * 80)
    print()

    print("rerank_meta:", result["rerank_meta"])
    print("rerank_hits:")
    for rank, hit in enumerate(result["rerank_hits"], start=1):
        print("-" * 80)
        print("rank:", rank)
        print("chunk_index:", hit["chunk_index"])
        print("score:", hit.get("score"))
        print("rerank_score:", hit.get("rerank_score"))
        print("faiss_score:", hit.get("faiss_score"))
        print("bm25_score:", hit.get("bm25_score"))
        print("rrf_score:", hit.get("rrf_score"))
        print(hit["content"])
    print("-" * 80)


def _chunks_for_llm(result):
    chunks = []
    for rank, hit in enumerate(result["rerank_hits"], start=1):
        content = hit.get("content") or ""
        chunks.append(
            {
                "rank": rank,
                "chunk_index": hit.get("chunk_index"),
                "score": hit.get("score"),
                "rerank_score": hit.get("rerank_score"),
                "faiss_score": hit.get("faiss_score"),
                "bm25_score": hit.get("bm25_score"),
                "rrf_score": hit.get("rrf_score"),
                "content": content,
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
                "回答要简洁、准确，不要评价切分策略。"
            ),
        },
        {
            "role": "user",
            "content": (
                "chunks:\n{0}\n\n"
                "问题：{1}\n\n"
                "请基于以上 chunks 回答问题。"
            ).format(
                json.dumps(_chunks_for_llm(result), ensure_ascii=False, indent=2),
                query,
            ),
        },
    ]


def _ask_vllm_with_chunks(url, headers, query, result):
    messages = _build_rag_messages(query, result)
    payload = {
        "model": "local-llm",
        "temperature": 0,
        "max_tokens": 512,
        "messages": messages,
    }

    response = http_client.post(url, headers=headers, json=payload, timeout=120)
    if response.status_code >= 400:
        raise RuntimeError(
            "vLLM chat completion failed strategy={0} status={1} body={2}".format(
                result["strategy"],
                response.status_code,
                response.text[:2000],
            )
        )
    data = response.json()
    answer = data["choices"][0]["message"]["content"]
    usage_metrics = build_usage_metrics(
        data.get("usage"),
        messages=messages,
        answer_text=answer,
    )
    return {
        "strategy": result["strategy"],
        "model": data.get("model") or payload["model"],
        "prompt_tokens_est": estimate_messages_tokens(messages),
        "completion_tokens_est": estimate_text_tokens(answer),
        "usage": usage_metrics,
        "answer": answer,
    }


def compare_results_with_vllm(query, title_result, simple_result):
    if not LLM_BASE_URL:
        raise RuntimeError("LLM_BASE_URL is not configured")

    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = "Bearer {0}".format(LLM_API_KEY)

    return {
        "title": _ask_vllm_with_chunks(url, headers, query, title_result),
        "simple": _ask_vllm_with_chunks(url, headers, query, simple_result),
    }


def compare_title_and_simple_recall(
    document_path,
    query,
    *,
    chunk_size=800,
    overlap=100,
    top_k=3,
):
    title_result = run_document_embedding_recall(
        document_path=document_path,
        query=query,
        strategy="title",
        chunk_size=chunk_size,
        overlap=overlap,
        top_k=top_k,
    )
    simple_result = run_document_embedding_recall(
        document_path=document_path,
        query=query,
        strategy="simple",
        chunk_size=chunk_size,
        overlap=overlap,
        top_k=top_k,
    )
    return title_result, simple_result


if __name__ == "__main__":
    path = "tests/data/merged.md"
    query = "智能指针所有权"

    title_result, simple_result = compare_title_and_simple_recall(
        document_path=path,
        query=query,
        chunk_size=800,
        overlap=100,
        top_k=3,
    )
    print_document_embedding_recall_result(title_result)
    print_document_embedding_recall_result(simple_result)

    print("=" * 100)
    print("vllm_answers:")
    compare_result = compare_results_with_vllm(query, title_result, simple_result)
    for name in ("title", "simple"):
        answer_result = compare_result[name]
        print("-" * 80)
        print("strategy:", answer_result["strategy"])
        print("model:", answer_result["model"])
        print("prompt_tokens_est:", answer_result["prompt_tokens_est"])
        print("completion_tokens_est:", answer_result["completion_tokens_est"])
        print("usage:", answer_result["usage"])
        print("answer:")
        print(answer_result["answer"])
