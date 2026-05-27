import math
import json
import time

from python_rag.config import (
    CHAT_CANDIDATE_TOP_K,
    RERANK_ENABLE,
    RETRIEVAL_CONTEXT_MAX_CHARS,
    RETRIEVAL_CONTEXT_WINDOW,
    RETRIEVAL_RECALL_PROVIDER,
)
from python_rag.core.error_codes import ERR_INDEX_NOT_FOUND, ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError
from python_rag.core.logger import logger

from python_rag.modules.documents.repo import get_document_index_by_doc_id, list_ready_document_ids
from python_rag.modules.ingest.embedding_service import (
    embed_query,
    get_embedding_model_name,
)
from python_rag.modules.monitor.request_metrics import (
    estimate_text_tokens,
    is_timeout_error,
    record_request_metric,
)
from python_rag.modules.retrieval.bm25_service import search_doc_bm25_index
from python_rag.modules.retrieval.faiss_service import search_doc_faiss_index
from python_rag.modules.retrieval.fusion_service import fuse_hits_with_rrf
from python_rag.modules.retrieval.reranker_service import rerank_hits


def _normalize_recall_provider():
    provider = (RETRIEVAL_RECALL_PROVIDER or "hybrid_rrf").strip().lower()
    if provider in ("hybrid", "hybrid_rrf", "rrf"):
        return "hybrid_rrf"
    if provider in ("bm25", "sparse"):
        return "bm25"
    if provider in ("faiss", "dense"):
        return "faiss"
    raise AppError(
        ERR_INTERNAL_ERROR,
        f"unsupported retrieval recall provider: {RETRIEVAL_RECALL_PROVIDER}",
        http_status=500,
    )


def _build_snippet(text, max_len=180):
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _load_mapping_by_chunk_index(mapping_path):
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    if not isinstance(mapping, list):
        return {}

    result = {}
    for item in mapping:
        if not isinstance(item, dict):
            continue
        chunk_index = item.get("chunk_index")
        if chunk_index is None:
            continue
        try:
            result[int(chunk_index)] = item
        except Exception:
            continue
    return result


def _truncate_context_text(text, max_chars):
    text = (text or "").strip()
    if not max_chars or max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[context truncated]"


def _merge_context_ranges(hits, context_window):
    ranges_by_doc_id = {}
    for hit in hits:
        doc_id = hit.get("doc_id")
        chunk_index = hit.get("chunk_index")
        try:
            normalized_doc_id = int(doc_id)
            center_index = int(chunk_index)
        except Exception:
            continue

        ranges_by_doc_id.setdefault(normalized_doc_id, []).append(
            {
                "start": center_index - context_window,
                "end": center_index + context_window,
                "matched_indexes": {center_index},
            }
        )

    merged_by_doc_id = {}
    for doc_id, ranges in ranges_by_doc_id.items():
        merged = []
        for item in sorted(ranges, key=lambda value: (value["start"], value["end"])):
            if not merged or item["start"] > merged[-1]["end"] + 1:
                merged.append(
                    {
                        "start": item["start"],
                        "end": item["end"],
                        "matched_indexes": set(item["matched_indexes"]),
                    }
                )
                continue

            merged[-1]["end"] = max(merged[-1]["end"], item["end"])
            merged[-1]["matched_indexes"].update(item["matched_indexes"])
        merged_by_doc_id[doc_id] = merged

    return merged_by_doc_id


def _find_context_range(context_ranges, chunk_index):
    for context_range in context_ranges:
        if context_range["start"] <= chunk_index <= context_range["end"]:
            return context_range
    return None


def _build_expanded_context_content(hit, mapping_by_chunk_index, context_range, max_chars):
    if not context_range:
        return None

    parts = []
    matched_indexes = context_range.get("matched_indexes", set())
    for index in range(context_range["start"], context_range["end"] + 1):
        item = mapping_by_chunk_index.get(index)
        if not item:
            continue

        content = (item.get("content") or item.get("text") or "").strip()
        if not content:
            continue

        label = "Matched" if index in matched_indexes else "Context"
        parts.append("[{0} chunk_index={1}]\n{2}".format(label, index, content))

    if not parts:
        return None
    return _truncate_context_text("\n\n".join(parts), max_chars)


def _expand_hits_with_neighbor_context(hits, index_metas):
    context_window = max(0, int(RETRIEVAL_CONTEXT_WINDOW or 0))
    if context_window <= 0 or not hits:
        return hits, {
            "enabled": False,
            "window": context_window,
            "expanded_count": 0,
            "failed_doc_ids": [],
        }

    max_chars = int(RETRIEVAL_CONTEXT_MAX_CHARS or 0)
    mapping_paths_by_doc_id = {
        int(item["doc_id"]): item["mapping_path"]
        for item in index_metas
        if item.get("doc_id") is not None and item.get("mapping_path")
    }
    merged_ranges_by_doc_id = _merge_context_ranges(hits, context_window)
    mapping_cache = {}
    failed_doc_ids = []
    expanded_hits = []
    expanded_count = 0

    for hit in hits:
        item = dict(hit)
        doc_id = item.get("doc_id")
        chunk_index = item.get("chunk_index")
        try:
            normalized_doc_id = int(doc_id)
            normalized_chunk_index = int(chunk_index)
        except Exception:
            expanded_hits.append(item)
            continue

        if normalized_doc_id not in mapping_cache:
            mapping_path = mapping_paths_by_doc_id.get(normalized_doc_id)
            try:
                mapping_cache[normalized_doc_id] = (
                    _load_mapping_by_chunk_index(mapping_path) if mapping_path else {}
                )
            except Exception:
                logger.exception(
                    "failed to load retrieval context mapping doc_id=%s",
                    normalized_doc_id,
                )
                mapping_cache[normalized_doc_id] = {}
                failed_doc_ids.append(normalized_doc_id)

        context_range = _find_context_range(
            merged_ranges_by_doc_id.get(normalized_doc_id, []),
            normalized_chunk_index,
        )
        expanded_content = _build_expanded_context_content(
            item,
            mapping_cache[normalized_doc_id],
            context_range=context_range,
            max_chars=max_chars,
        )
        if expanded_content and expanded_content != (item.get("content") or "").strip():
            item["original_content"] = item.get("content", "")
            item["content"] = expanded_content
            item["snippet"] = _build_snippet(expanded_content)
            item["context_window"] = context_window
            expanded_count += 1

        expanded_hits.append(item)

    return expanded_hits, {
        "enabled": True,
        "window": context_window,
        "max_chars": max_chars,
        "expanded_count": expanded_count,
        "failed_doc_ids": sorted(set(failed_doc_ids)),
    }

def _format_faiss_hit(item):
    content = item.get("content", "")
    score = round(float(item["score"]), 6)
    return {
        "doc_id": item["doc_id"],
        "chunk_id": item["chunk_id"],
        "chunk_index": item["chunk_index"],
        "score": score,
        "faiss_score": score,
        "content": content,
        "snippet": _build_snippet(content),
    }


def _format_bm25_hit(item):
    content = item.get("content", "")
    score = round(float(item["bm25_score"]), 6)
    return {
        "doc_id": item["doc_id"],
        "chunk_id": item["chunk_id"],
        "chunk_index": item["chunk_index"],
        "score": score,
        "bm25_score": score,
        "content": content,
        "snippet": _build_snippet(content),
    }


def _rank_source_hits(hits, score_field, rank_field):
    hits.sort(
        key=lambda item: item.get(score_field) if item.get(score_field) is not None else float("-inf"),
        reverse=True,
    )
    for rank, item in enumerate(hits, start=1):
        item[rank_field] = rank
    return hits


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


def resolve_search_doc_ids(doc_id=None, doc_ids=None, user_id=None, embedding_model=None):
    resolved_doc_ids = []
    seen = set()

    def add_doc_id(value):
        if value is None:
            return
        parsed = int(value)
        if parsed <= 0:
            return
        if parsed in seen:
            return
        seen.add(parsed)
        resolved_doc_ids.append(parsed)

    add_doc_id(doc_id)
    for item in doc_ids or []:
        add_doc_id(item)

    if not resolved_doc_ids:
        resolved_doc_ids = list_ready_document_ids(
            user_id=user_id,
            embedding_model=embedding_model,
            limit=1000,
        )

    if not resolved_doc_ids:
        raise AppError(ERR_INDEX_NOT_FOUND, "no ready document index found")

    return resolved_doc_ids


def _load_ready_index_meta(doc_id, current_embedding_model):
    index_meta = get_document_index_by_doc_id(doc_id)
    if not index_meta:
        raise AppError(ERR_INDEX_NOT_FOUND, "document index not found: doc_id=%s" % doc_id)

    if index_meta["status"] != "READY":
        raise AppError(ERR_INTERNAL_ERROR, "document index is not ready: doc_id=%s" % doc_id)

    if index_meta.get("embedding_model") != current_embedding_model:
        raise AppError(
            ERR_INTERNAL_ERROR,
            (
                "document index embedding mismatch: doc_id=%s indexed_with='%s', current='%s'. "
                "Re-ingest the document before querying."
            )
            % (doc_id, index_meta.get("embedding_model"), current_embedding_model),
            http_status=409,
        )

    return index_meta


def search_in_documents(
    query,
    doc_ids=None,
    doc_id=None,
    user_id=None,
    top_k=3,
    candidate_top_k=None,
    track_metric=True,
    relevant_chunk_ids=None,
    relevant_chunk_indexes=None,
):
    started_at = time.perf_counter()
    embedding_ms = None
    faiss_ms = None
    bm25_ms = None
    rrf_ms = None
    doc_faiss_ms = {}
    doc_bm25_ms = {}
    rerank_ms = None
    rerank_meta = {}
    context_expansion_meta = {}
    resolved_doc_ids = []
    recall_provider = _normalize_recall_provider()
    use_faiss = recall_provider in ("faiss", "hybrid_rrf")
    use_bm25 = recall_provider in ("bm25", "hybrid_rrf")
    final_top_k = max(1, int(top_k or 1))
    configured_candidate_top_k = int(candidate_top_k or CHAT_CANDIDATE_TOP_K)
    effective_candidate_top_k = (
        max(final_top_k, configured_candidate_top_k)
        if RERANK_ENABLE
        else final_top_k
    )

    try:
        current_embedding_model = get_embedding_model_name()
        resolved_doc_ids = resolve_search_doc_ids(
            doc_id=doc_id,
            doc_ids=doc_ids,
            user_id=user_id,
            embedding_model=current_embedding_model,
        )
        index_metas = [
            _load_ready_index_meta(item, current_embedding_model)
            for item in resolved_doc_ids
        ]

        query_vector = None
        if use_faiss:
            embedding_started_at = time.perf_counter()
            query_vector = embed_query(query)
            embedding_ms = int((time.perf_counter() - embedding_started_at) * 1000)

        faiss_hits = []
        bm25_hits = []
        for index_meta in index_metas:
            if use_faiss:
                doc_search_started_at = time.perf_counter()
                hits = search_doc_faiss_index(
                    index_path=index_meta["index_path"],
                    mapping_path=index_meta["mapping_path"],
                    query_vector=query_vector,
                    top_k=effective_candidate_top_k,
                )
                elapsed_ms = int((time.perf_counter() - doc_search_started_at) * 1000)
                doc_faiss_ms[str(index_meta["doc_id"])] = elapsed_ms
                faiss_ms = (faiss_ms or 0) + elapsed_ms
                faiss_hits.extend(_format_faiss_hit(item) for item in hits)

            if use_bm25:
                doc_search_started_at = time.perf_counter()
                hits = search_doc_bm25_index(
                    mapping_path=index_meta["mapping_path"],
                    query=query,
                    top_k=effective_candidate_top_k,
                )
                elapsed_ms = int((time.perf_counter() - doc_search_started_at) * 1000)
                doc_bm25_ms[str(index_meta["doc_id"])] = elapsed_ms
                bm25_ms = (bm25_ms or 0) + elapsed_ms
                bm25_hits.extend(_format_bm25_hit(item) for item in hits)

        candidate_hits = []
        if recall_provider == "hybrid_rrf":
            _rank_source_hits(faiss_hits, "faiss_score", "faiss_rank")
            _rank_source_hits(bm25_hits, "bm25_score", "bm25_rank")
            rrf_started_at = time.perf_counter()
            candidate_hits = fuse_hits_with_rrf(
                [("bm25", bm25_hits), ("faiss", faiss_hits)],
                limit=effective_candidate_top_k * max(1, len(index_metas)),
            )
            rrf_ms = int((time.perf_counter() - rrf_started_at) * 1000)
        elif recall_provider == "bm25":
            candidate_hits = _rank_source_hits(bm25_hits, "bm25_score", "bm25_rank")
        else:
            candidate_hits = _rank_source_hits(faiss_hits, "faiss_score", "faiss_rank")

        rerank_started_at = time.perf_counter()
        result_hits, rerank_meta = rerank_hits(
            query=query,
            hits=candidate_hits,
            final_top_k=final_top_k,
            recall_provider=recall_provider,
        )
        rerank_meta.update(
            {
                "recall_provider": recall_provider,
                "bm25_candidate_count": len(bm25_hits),
                "faiss_candidate_count": len(faiss_hits),
                "rrf_candidate_count": len(candidate_hits) if recall_provider == "hybrid_rrf" else None,
            }
        )
        rerank_ms = int((time.perf_counter() - rerank_started_at) * 1000)

        eval_metrics = _evaluate_retrieval_hits(
            result_hits,
            relevant_chunk_ids=relevant_chunk_ids,
            relevant_chunk_indexes=relevant_chunk_indexes,
        )
        result_hits, context_expansion_meta = _expand_hits_with_neighbor_context(
            result_hits,
            index_metas,
        )

        retrieval_ms = int((time.perf_counter() - started_at) * 1000)
        result = {
            "doc_id": resolved_doc_ids[0] if len(resolved_doc_ids) == 1 else None,
            "doc_ids": resolved_doc_ids,
            "doc_count": len(resolved_doc_ids),
            "query": query,
            "top_k": final_top_k,
            "candidate_top_k": effective_candidate_top_k,
            "hits": result_hits,
            "metrics": {
                "embedding_ms": embedding_ms,
                "faiss_ms": faiss_ms,
                "bm25_ms": bm25_ms,
                "rrf_ms": rrf_ms,
                "rerank_ms": rerank_ms,
                "retrieval_ms": retrieval_ms,
                "doc_faiss_ms": doc_faiss_ms,
                "doc_bm25_ms": doc_bm25_ms,
                "candidate_top_k": effective_candidate_top_k,
                "final_top_k": final_top_k,
                "recall_provider": recall_provider,
                "candidate_count": len(candidate_hits),
                "bm25_candidate_count": len(bm25_hits),
                "faiss_candidate_count": len(faiss_hits),
                "rerank": rerank_meta,
                "context_expansion": context_expansion_meta,
                **eval_metrics,
            },
        }

        if track_metric:
            record_request_metric(
                request_type="retrieval",
                status="success",
                channel="http",
                doc_id=resolved_doc_ids[0] if len(resolved_doc_ids) == 1 else None,
                top_k=final_top_k,
                retrieval_ms=retrieval_ms,
                embedding_tokens=estimate_text_tokens(query) if use_faiss else 0,
                cost_usd=0.0,
                extra={
                    "embedding_ms": embedding_ms,
                    "faiss_ms": faiss_ms,
                    "bm25_ms": bm25_ms,
                    "rrf_ms": rrf_ms,
                    "doc_faiss_ms": doc_faiss_ms,
                    "doc_bm25_ms": doc_bm25_ms,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": effective_candidate_top_k,
                    "final_top_k": final_top_k,
                    "recall_provider": recall_provider,
                    "hit_count": len(result_hits),
                    "candidate_count": len(candidate_hits),
                    "bm25_candidate_count": len(bm25_hits),
                    "faiss_candidate_count": len(faiss_hits),
                    "doc_ids": resolved_doc_ids,
                    "doc_count": len(resolved_doc_ids),
                    "rerank": rerank_meta,
                    "context_expansion": context_expansion_meta,
                    **eval_metrics,
                },
            )

        return result
    except Exception as exc:
        retrieval_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "search_in_documents failed doc_ids=%s top_k=%s retrieval_ms=%s",
            resolved_doc_ids or doc_ids or doc_id,
            final_top_k,
            retrieval_ms,
        )
        if track_metric:
            record_request_metric(
                request_type="retrieval",
                status="error",
                channel="http",
                doc_id=resolved_doc_ids[0] if len(resolved_doc_ids) == 1 else None,
                top_k=final_top_k,
                retrieval_ms=retrieval_ms,
                timed_out=is_timeout_error(exc),
                error_message=str(exc),
                extra={
                    "embedding_ms": embedding_ms,
                    "faiss_ms": faiss_ms,
                    "bm25_ms": bm25_ms,
                    "rrf_ms": rrf_ms,
                    "doc_faiss_ms": doc_faiss_ms,
                    "doc_bm25_ms": doc_bm25_ms,
                    "rerank_ms": rerank_ms,
                    "candidate_top_k": effective_candidate_top_k,
                    "final_top_k": final_top_k,
                    "recall_provider": recall_provider,
                    "doc_ids": resolved_doc_ids,
                    "doc_count": len(resolved_doc_ids),
                    "rerank": rerank_meta,
                    "context_expansion": context_expansion_meta,
                },
            )
        raise


def search_in_document(
    doc_id,
    query,
    top_k=3,
    candidate_top_k=None,
    track_metric=True,
    relevant_chunk_ids=None,
    relevant_chunk_indexes=None,
):
    return search_in_documents(
        query=query,
        doc_id=doc_id,
        top_k=top_k,
        candidate_top_k=candidate_top_k,
        track_metric=track_metric,
        relevant_chunk_ids=relevant_chunk_ids,
        relevant_chunk_indexes=relevant_chunk_indexes,
    )
