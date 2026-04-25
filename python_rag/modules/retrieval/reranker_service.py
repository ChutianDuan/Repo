from typing import Any, Dict, List, Tuple

import numpy as np
import torch

from python_rag.config import (
    RERANK_BATCH_SIZE,
    RERANK_DEVICE,
    RERANK_ENABLE,
    RERANK_FALLBACK_TO_FAISS,
    RERANK_MODEL,
    RERANK_PROVIDER,
)
from python_rag.core.error_codes import ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError
from python_rag.core.logger import logger


_cross_encoder_model = None
_cross_encoder_init_error = None


def _resolve_device() -> str:
    if RERANK_DEVICE and RERANK_DEVICE != "auto":
        return RERANK_DEVICE
    return "cuda" if torch.cuda.is_available() else "cpu"


def _get_cross_encoder_model():
    global _cross_encoder_model, _cross_encoder_init_error
    if _cross_encoder_init_error is not None:
        raise AppError(
            ERR_INTERNAL_ERROR,
            _cross_encoder_init_error,
            http_status=500,
        )

    if _cross_encoder_model is None:
        try:
            from sentence_transformers import CrossEncoder
        except Exception as exc:
            raise AppError(
                ERR_INTERNAL_ERROR,
                f"reranker dependencies are not available: {exc}",
                http_status=500,
            ) from exc

        try:
            _cross_encoder_model = CrossEncoder(
                RERANK_MODEL,
                device=_resolve_device(),
            )
        except Exception as exc:
            _cross_encoder_init_error = (
                "failed to initialize reranker model "
                f"'{RERANK_MODEL}' with provider '{RERANK_PROVIDER}': {exc}"
            )
            raise AppError(
                ERR_INTERNAL_ERROR,
                _cross_encoder_init_error,
                http_status=500,
            ) from exc
    return _cross_encoder_model


def _score_with_cross_encoder(query: str, hits: List[Dict[str, Any]]) -> np.ndarray:
    model = _get_cross_encoder_model()
    pairs = [(query, hit.get("content") or hit.get("snippet") or "") for hit in hits]
    scores = model.predict(
        pairs,
        batch_size=RERANK_BATCH_SIZE,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    scores = np.asarray(scores, dtype="float32").reshape(-1)
    if scores.shape[0] != len(hits):
        raise AppError(
            ERR_INTERNAL_ERROR,
            "reranker response count mismatch: expected=%s actual=%s"
            % (len(hits), scores.shape[0]),
            http_status=500,
        )
    return scores


def _with_ranks(hits: List[Dict[str, Any]], final_top_k: int) -> List[Dict[str, Any]]:
    result = []
    for rank, hit in enumerate(hits[:final_top_k], start=1):
        item = dict(hit)
        item["rank"] = rank
        if "faiss_score" not in item and item.get("score") is not None:
            item["faiss_score"] = item.get("score")
        result.append(item)
    return result


def _faiss_fallback(
    hits: List[Dict[str, Any]],
    final_top_k: int,
    meta: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    meta.update(
        {
            "enabled": False,
            "used": False,
            "fallback": True,
            "provider": "faiss",
            "model": None,
        }
    )
    return _with_ranks(hits, final_top_k), meta


def rerank_hits(
    query: str,
    hits: List[Dict[str, Any]],
    final_top_k: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    meta: Dict[str, Any] = {
        "enabled": bool(RERANK_ENABLE),
        "used": False,
        "fallback": False,
        "provider": RERANK_PROVIDER,
        "model": RERANK_MODEL if RERANK_ENABLE else None,
        "candidate_count": len(hits),
        "returned_count": 0,
    }

    if final_top_k <= 0 or not hits:
        return [], meta

    if not RERANK_ENABLE or RERANK_PROVIDER in ("", "none", "faiss"):
        ranked_hits = _with_ranks(hits, final_top_k)
        meta.update(
            {
                "enabled": False,
                "provider": "faiss",
                "model": None,
                "returned_count": len(ranked_hits),
            }
        )
        return ranked_hits, meta

    try:
        if RERANK_PROVIDER != "cross_encoder":
            raise AppError(
                ERR_INTERNAL_ERROR,
                f"unsupported reranker provider: {RERANK_PROVIDER}",
                http_status=500,
            )

        scores = _score_with_cross_encoder(query=query, hits=hits)
        scored_hits = []
        for original_rank, (hit, rerank_score) in enumerate(zip(hits, scores), start=1):
            item = dict(hit)
            item["original_rank"] = original_rank
            item["faiss_score"] = item.get("score")
            item["rerank_score"] = round(float(rerank_score), 6)
            scored_hits.append(item)

        scored_hits.sort(
            key=lambda item: (
                item.get("rerank_score") if item.get("rerank_score") is not None else float("-inf"),
                item.get("score") if item.get("score") is not None else float("-inf"),
            ),
            reverse=True,
        )
        ranked_hits = _with_ranks(scored_hits, final_top_k)
        meta.update(
            {
                "used": True,
                "fallback": False,
                "returned_count": len(ranked_hits),
            }
        )
        return ranked_hits, meta
    except Exception as exc:
        if not RERANK_FALLBACK_TO_FAISS:
            raise

        logger.exception(
            "rerank failed provider=%s model=%s candidate_count=%s; falling back to faiss order",
            RERANK_PROVIDER,
            RERANK_MODEL,
            len(hits),
        )
        meta["error"] = str(exc)
        ranked_hits, meta = _faiss_fallback(hits, final_top_k, meta)
        meta["returned_count"] = len(ranked_hits)
        return ranked_hits, meta
