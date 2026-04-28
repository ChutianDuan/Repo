import math
import time

from python_rag.config import CHAT_CANDIDATE_TOP_K, RERANK_ENABLE
from python_rag.core.error_codes import ERR_INDEX_NOT_FOUND, ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError
from python_rag.core.logger import logger

from python_rag.modules.documents.repo import get_document_index_by_doc_id
from python_rag.modules.ingest.embedding_service import (
    embed_query,
    get_embedding_model_name,
)
from python_rag.modules.monitor.request_metrics import (
    estimate_text_tokens,
    is_timeout_error,
    record_request_metric,
)
from python_rag.modules.retrieval.faiss_service import search_doc_faiss_index
from python_rag.modules.retrieval.reranker_service import rerank_hits


def _build_snippet(text, max_len=180):
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _evaluate_retrieval_hits(hits, relevant_chunk_ids=None, relevant_chunk_indexes=None):
    relevant_ids = {int(item) for item in relevant_chunk_ids or [] if item is not None}
    relevant_indexes = {int(item) for item in relevant_chunk_indexes or [] if item is not None}
    relevant_count = len(relevant_ids) + len(relevant_indexes)
    if relevant_count <= 0:
        return {}

    matched = 0
    first_relevant_rank = None
    dcg = 0.0
    for rank, hit in enumerate(hits, start=1):
        chunk_id = hit.get("chunk_id")
        chunk_index = hit.get("chunk_index")
        is_relevant = (
            (chunk_id is not None and int(chunk_id) in relevant_ids)
            or (chunk_index is not None and int(chunk_index) in relevant_indexes)
        )
        if not is_relevant:
            continue

        matched += 1
        if first_relevant_rank is None:
            first_relevant_rank = rank
        dcg += 1.0 / math.log2(rank + 1)

    ideal_hits = min(relevant_count, len(hits))
    ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))

    return {
        "relevant_count": relevant_count,
        "relevant_hit_count": matched,
        "recall_at_k": round(matched / relevant_count, 6),
        "mrr": round(1.0 / first_relevant_rank, 6) if first_relevant_rank else 0.0,
        "ndcg": round(dcg / ideal_dcg, 6) if ideal_dcg > 0 else None,
    }


def search_in_document(
    doc_id,
    query,
    top_k=3,
    candidate_top_k=None,
    track_metric=True,
    relevant_chunk_ids=None,
    relevant_chunk_indexes=None,
):
    started_at = time.perf_counter()
    embedding_started_at = time.perf_counter()
    embedding_ms = None
    faiss_ms = None
    rerank_ms = None
    rerank_meta = {}
    final_top_k = max(1, int(top_k or 1))
    configured_candidate_top_k = int(candidate_top_k or CHAT_CANDIDATE_TOP_K)
    effective_candidate_top_k = (
        max(final_top_k, configured_candidate_top_k)
        if RERANK_ENABLE
        else final_top_k
    )

    try:
        index_meta = get_document_index_by_doc_id(doc_id)
        if not index_meta:
            raise AppError(ERR_INDEX_NOT_FOUND, "document index not found")

        if index_meta["status"] != "READY":
            raise AppError(ERR_INTERNAL_ERROR, "document index is not ready")

        current_embedding_model = get_embedding_model_name()
        if index_meta.get("embedding_model") != current_embedding_model:
            raise AppError(
                ERR_INTERNAL_ERROR,
                (
                    "document index embedding mismatch: indexed_with='%s', current='%s'. "
                    "Re-ingest the document before querying."
                )
                % (index_meta.get("embedding_model"), current_embedding_model),
                http_status=409,
            )

        query_vector = embed_query(query)
        embedding_ms = int((time.perf_counter() - embedding_started_at) * 1000)

        faiss_started_at = time.perf_counter()
        hits = search_doc_faiss_index(
            index_path=index_meta["index_path"],
            mapping_path=index_meta["mapping_path"],
            query_vector=query_vector,
            top_k=effective_candidate_top_k,
        )
        faiss_ms = int((time.perf_counter() - faiss_started_at) * 1000)

        candidate_hits = []
        for item in hits:
            content = item.get("content", "")
            score = round(float(item["score"]), 6)
            candidate_hits.append(
                {
                    "doc_id": item["doc_id"],
                    "chunk_id": item["chunk_id"],
                    "chunk_index": item["chunk_index"],
                    "score": score,
                    "faiss_score": score,
                    "content": content,
                    "snippet": _build_snippet(content),
                }
            )

        rerank_started_at = time.perf_counter()
        result_hits, rerank_meta = rerank_hits(
            query=query,
            hits=candidate_hits,
            final_top_k=final_top_k,
        )
        rerank_ms = int((time.perf_counter() - rerank_started_at) * 1000)

        retrieval_ms = int((time.perf_counter() - started_at) * 1000)
        eval_metrics = _evaluate_retrieval_hits(
            result_hits,
            relevant_chunk_ids=relevant_chunk_ids,
            relevant_chunk_indexes=relevant_chunk_indexes,
        )
        result = {
            "doc_id": doc_id,
            "query": query,
            "top_k": final_top_k,
            "candidate_top_k": effective_candidate_top_k,
            "hits": result_hits,
            "metrics": {
                "embedding_ms": embedding_ms,
                "faiss_ms": faiss_ms,
                "rerank_ms": rerank_ms,
                "retrieval_ms": retrieval_ms,
                "candidate_top_k": effective_candidate_top_k,
                "final_top_k": final_top_k,
                "rerank": rerank_meta,
                **eval_metrics,
            },
        }

        if track_metric:
            record_request_metric(
                request_type="retrieval",
                status="success",
                channel="http",
                doc_id=doc_id,
                top_k=final_top_k,
                retrieval_ms=retrieval_ms,
                embedding_tokens=estimate_text_tokens(query),
                cost_usd=0.0,
                extra={
                    "embedding_ms": embedding_ms,
                    "faiss_ms": faiss_ms,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": effective_candidate_top_k,
                    "final_top_k": final_top_k,
                    "hit_count": len(result_hits),
                    "candidate_count": len(candidate_hits),
                    "rerank": rerank_meta,
                    **eval_metrics,
                },
            )

        return result
    except Exception as exc:
        retrieval_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "search_in_document failed doc_id=%s top_k=%s retrieval_ms=%s",
            doc_id,
            final_top_k,
            retrieval_ms,
        )
        if track_metric:
            record_request_metric(
                request_type="retrieval",
                status="error",
                channel="http",
                doc_id=doc_id,
                top_k=final_top_k,
                retrieval_ms=retrieval_ms,
                timed_out=is_timeout_error(exc),
                error_message=str(exc),
                extra={
                    "embedding_ms": embedding_ms,
                    "faiss_ms": faiss_ms,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": effective_candidate_top_k,
                    "final_top_k": final_top_k,
                    "rerank": rerank_meta,
                },
            )
        raise
