from typing import Any, Dict, Iterable, List, Optional, Tuple

from python_rag.app.core.config import RRF_K


def _hit_key(hit: Dict[str, Any]) -> Tuple[Any, Any]:
    return hit.get("doc_id"), hit.get("chunk_id")


def fuse_hits_with_rrf(
    ranked_hit_lists: Iterable[Tuple[str, List[Dict[str, Any]]]],
    *,
    limit: Optional[int] = None,
    rrf_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    k = RRF_K if rrf_k is None else rrf_k
    fused: Dict[Tuple[Any, Any], Dict[str, Any]] = {}

    for source, hits in ranked_hit_lists:
        source = (source or "").strip().lower()
        if not source or not hits:
            continue

        for rank, hit in enumerate(hits, start=1):
            key = _hit_key(hit)
            if key[0] is None or key[1] is None:
                continue

            item = fused.get(key)
            if item is None:
                item = dict(hit)
                item["rrf_score"] = 0.0
                item["rrf_sources"] = []
                fused[key] = item

            item["rrf_score"] += 1.0 / (k + rank)
            item["rrf_sources"].append(source)
            item[f"{source}_rank"] = rank

            if source == "bm25":
                item["bm25_score"] = hit.get("bm25_score", hit.get("score"))
            elif source == "faiss":
                item["faiss_score"] = hit.get("faiss_score", hit.get("score"))

            if not item.get("content") and hit.get("content"):
                item["content"] = hit["content"]
            if not item.get("snippet") and hit.get("snippet"):
                item["snippet"] = hit["snippet"]

    ranked = sorted(
        fused.values(),
        key=lambda item: (
            item.get("rrf_score") if item.get("rrf_score") is not None else float("-inf"),
            item.get("bm25_score") if item.get("bm25_score") is not None else float("-inf"),
            item.get("faiss_score") if item.get("faiss_score") is not None else float("-inf"),
        ),
        reverse=True,
    )

    result = ranked[:limit] if limit is not None else ranked
    for rank, item in enumerate(result, start=1):
        item["rrf_rank"] = rank
        item["score"] = round(float(item.get("rrf_score") or 0.0), 6)
        item["rrf_score"] = item["score"]
    return result
