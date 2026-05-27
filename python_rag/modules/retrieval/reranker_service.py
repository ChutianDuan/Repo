from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from python_rag.config import (
    RERANK_BATCH_SIZE,
    RERANK_CACHE_DIR,
    RERANK_DEVICE,
    RERANK_DOWNLOAD_IF_MISSING,
    RERANK_ENABLE,
    RERANK_FALLBACK_TO_FAISS,
    RERANK_LOCAL_FILES_ONLY,
    RERANK_MODEL,
    RERANK_PROVIDER,
)
from python_rag.core.error_codes import ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError
from python_rag.core.logger import logger


_cross_encoder_model = None
_cross_encoder_init_error = None
_MODEL_WEIGHT_FILENAMES = (
    "pytorch_model.bin",
    "model.safetensors",
    "tf_model.h5",
    "model.ckpt.index",
    "flax_model.msgpack",
    "pytorch_model.bin.index.json",
    "model.safetensors.index.json",
)


def _is_local_model_path(model_name: str) -> bool:
    if not model_name:
        return False
    return Path(model_name).expanduser().exists()


def _snapshot_download(
    model_name: str,
    *,
    cache_dir: Optional[str],
    local_files_only: bool,
    force_download: bool = False,
) -> str:
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        raise AppError(
            ERR_INTERNAL_ERROR,
            f"huggingface_hub is not available for reranker cache resolution: {exc}",
            http_status=500,
        ) from exc

    return snapshot_download(
        repo_id=model_name,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        force_download=force_download,
    )


def _has_model_weight_file(model_path: str) -> bool:
    path = Path(model_path).expanduser()
    if not path.is_dir():
        return True
    return any((path / filename).exists() for filename in _MODEL_WEIGHT_FILENAMES)


def _raise_incomplete_model_cache(model_name: str, model_path: str):
    raise AppError(
        ERR_INTERNAL_ERROR,
        (
            "reranker model cache is incomplete: "
            f"model='{model_name}' path='{model_path}'. "
            "Missing model weights. Set RERANK_DOWNLOAD_IF_MISSING=true "
            "or delete the incomplete Hugging Face cache snapshot and retry."
        ),
        http_status=500,
    )


def _download_cross_encoder_snapshot(
    model_name: str,
    *,
    cache_dir: Optional[str],
    force_download: bool,
) -> str:
    model_path = _snapshot_download(
        model_name,
        cache_dir=cache_dir,
        local_files_only=False,
        force_download=force_download,
    )
    if not _has_model_weight_file(model_path):
        _raise_incomplete_model_cache(model_name, model_path)
    return model_path


def _resolve_cross_encoder_model_path(model_name: str) -> str:
    if not model_name:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "RERANK_MODEL is not configured",
            http_status=500,
        )

    if _is_local_model_path(model_name):
        model_path = str(Path(model_name).expanduser())
        if not _has_model_weight_file(model_path):
            _raise_incomplete_model_cache(model_name, model_path)
        return model_path

    cache_dir = RERANK_CACHE_DIR
    if not RERANK_LOCAL_FILES_ONLY:
        return model_name

    try:
        model_path = _snapshot_download(
            model_name,
            cache_dir=cache_dir,
            local_files_only=True,
        )
        if _has_model_weight_file(model_path):
            return model_path

        if not RERANK_DOWNLOAD_IF_MISSING:
            _raise_incomplete_model_cache(model_name, model_path)

        logger.warning(
            "reranker model cache snapshot is incomplete; redownloading model=%s path=%s cache_dir=%s",
            model_name,
            model_path,
            cache_dir,
        )
        return _download_cross_encoder_snapshot(
            model_name,
            cache_dir=cache_dir,
            force_download=True,
        )
    except AppError:
        raise
    except Exception as cache_exc:
        if not RERANK_DOWNLOAD_IF_MISSING:
            raise AppError(
                ERR_INTERNAL_ERROR,
                (
                    "reranker model is not available in local cache: "
                    f"model='{model_name}' cache_dir='{cache_dir}'. "
                    "Set RERANK_DOWNLOAD_IF_MISSING=true or pre-download the model."
                ),
                http_status=500,
            ) from cache_exc

        logger.warning(
            "reranker model cache miss; downloading snapshot model=%s cache_dir=%s",
            model_name,
            cache_dir,
        )
        return _download_cross_encoder_snapshot(
            model_name,
            cache_dir=cache_dir,
            force_download=False,
        )


def _build_cross_encoder_kwargs(model_path: str, device: str) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "device": device,
        "local_files_only": RERANK_LOCAL_FILES_ONLY,
        "config_args": {
            # Some cached reranker configs contain null in `architectures`.
            # sentence-transformers CrossEncoder calls `.endswith()` on each item.
            "architectures": ["AutoModelForSequenceClassification"],
        },
    }
    if RERANK_CACHE_DIR and not _is_local_model_path(model_path):
        kwargs["cache_dir"] = RERANK_CACHE_DIR
    return kwargs


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
            device = _resolve_device()
            model_path = _resolve_cross_encoder_model_path(RERANK_MODEL)
            logger.info(
                "initializing reranker model provider=%s model=%s resolved_model=%s device=%s local_files_only=%s cache_dir=%s",
                RERANK_PROVIDER,
                RERANK_MODEL,
                model_path,
                device,
                RERANK_LOCAL_FILES_ONLY,
                RERANK_CACHE_DIR,
            )
            _cross_encoder_model = CrossEncoder(
                model_path,
                **_build_cross_encoder_kwargs(model_path, device),
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
        logger.info(
            "reranker model initialized provider=%s model=%s",
            RERANK_PROVIDER,
            RERANK_MODEL,
        )
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
        if (
            "faiss_score" not in item
            and "bm25_score" not in item
            and "rrf_score" not in item
            and item.get("score") is not None
        ):
            item["faiss_score"] = item.get("score")
        result.append(item)
    return result


def _recall_order_fallback(
    hits: List[Dict[str, Any]],
    final_top_k: int,
    meta: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    meta.update(
        {
            "enabled": False,
            "used": False,
            "fallback": True,
            "fallback_provider": meta.get("recall_provider", "input_order"),
            "model": None,
        }
    )
    return _with_ranks(hits, final_top_k), meta


def rerank_hits(
    query: str,
    hits: List[Dict[str, Any]],
    final_top_k: int,
    recall_provider: str = "faiss",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    meta: Dict[str, Any] = {
        "enabled": bool(RERANK_ENABLE),
        "used": False,
        "fallback": False,
        "provider": RERANK_PROVIDER,
        "model": RERANK_MODEL if RERANK_ENABLE else None,
        "recall_provider": recall_provider,
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
                "provider": "none",
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
            if (
                "faiss_score" not in item
                and "bm25_score" not in item
                and "rrf_score" not in item
            ):
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
            "rerank failed provider=%s model=%s candidate_count=%s; falling back to recall order",
            RERANK_PROVIDER,
            RERANK_MODEL,
            len(hits),
        )
        meta["error"] = str(exc)
        ranked_hits, meta = _recall_order_fallback(hits, final_top_k, meta)
        meta["returned_count"] = len(ranked_hits)
        return ranked_hits, meta
