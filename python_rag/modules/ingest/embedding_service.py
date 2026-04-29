import logging
import os
from typing import Dict, List

import numpy as np
import requests
import torch

from python_rag.config import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DEVICE,
    EMBEDDING_DOCUMENT_PREFIX,
    EMBEDDING_MODEL,
    EMBEDDING_NORMALIZE,
    EMBEDDING_PROVIDER,
    EMBEDDING_QUERY_PREFIX,
    EMBEDDING_TIMEOUT_SECONDS,
)
from python_rag.core.error_codes import ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError


logger = logging.getLogger(__name__)
_model = None


def _resolve_device() -> str:
    if EMBEDDING_DEVICE and EMBEDDING_DEVICE != "auto":
        return EMBEDDING_DEVICE
    return "cuda" if torch.cuda.is_available() else "cpu"


def _normalize_text(text: str) -> str:
    return " ".join((text or "").replace("\r", " ").replace("\n", " ").split()).strip()


def _normalize_prefix(prefix: str) -> str:
    return (prefix or "").replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")


def _prefix_text(prefix: str, text: str) -> str:
    text = _normalize_text(text)
    prefix = _normalize_prefix(prefix)
    if not prefix:
        return text
    return prefix + text


def get_embedding_model_name() -> str:
    return EMBEDDING_MODEL


def get_embedding_provider() -> str:
    return EMBEDDING_PROVIDER


def format_document_for_embedding(text: str) -> str:
    return _prefix_text(EMBEDDING_DOCUMENT_PREFIX, text)


def format_query_for_embedding(text: str) -> str:
    return _prefix_text(EMBEDDING_QUERY_PREFIX, text)


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.clip(norms, a_min=1e-12, a_max=None)
    return vectors / norms


def _build_headers() -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
    }
    if EMBEDDING_API_KEY:
        headers["Authorization"] = "Bearer %s" % EMBEDDING_API_KEY
    return headers


def _get_sentence_transformer_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise AppError(
                ERR_INTERNAL_ERROR,
                f"embedding dependencies are not available: {exc}",
                http_status=500,
            ) from exc

        try:
            device = _resolve_device()
            logger.info(
                "initializing embedding model provider=%s model=%s requested_device=%s resolved_device=%s cuda_visible_devices=%s",
                EMBEDDING_PROVIDER,
                EMBEDDING_MODEL,
                EMBEDDING_DEVICE,
                device,
                os.environ.get("CUDA_VISIBLE_DEVICES"),
            )
            _model = SentenceTransformer(EMBEDDING_MODEL, device=device)
        except Exception as exc:
            raise AppError(
                ERR_INTERNAL_ERROR,
                (
                    "failed to initialize embedding model "
                    f"'{EMBEDDING_MODEL}' with provider '{EMBEDDING_PROVIDER}': {exc}"
                ),
                http_status=500,
            ) from exc
    return _model


def _embed_via_sentence_transformers(texts: List[str]) -> np.ndarray:
    model = _get_sentence_transformer_model()
    embeddings = model.encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=EMBEDDING_NORMALIZE,
    )
    return embeddings.astype("float32")


def _embed_via_openai_compatible(texts: List[str]) -> np.ndarray:
    if not EMBEDDING_BASE_URL:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "EMBEDDING_BASE_URL is not configured for openai_compatible provider",
            http_status=500,
        )

    if not EMBEDDING_MODEL:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "EMBEDDING_MODEL is not configured",
            http_status=500,
        )

    url = EMBEDDING_BASE_URL + "/embeddings"
    payload = {
        "model": EMBEDDING_MODEL,
        "input": texts,
        "encoding_format": "float",
    }

    try:
        response = requests.post(
            url,
            headers=_build_headers(),
            json=payload,
            timeout=EMBEDDING_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise AppError(
            ERR_INTERNAL_ERROR,
            f"embedding request failed: {exc}",
            http_status=502,
        ) from exc

    if response.status_code >= 400:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "embedding http error status=%s body=%s"
            % (response.status_code, response.text[:1000]),
            http_status=502,
        )

    try:
        resp_json = response.json()
    except ValueError as exc:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "embedding response is not valid json: %s" % response.text[:1000],
            http_status=502,
        ) from exc

    rows = resp_json.get("data") or []
    if len(rows) != len(texts):
        raise AppError(
            ERR_INTERNAL_ERROR,
            "embedding response count mismatch: expected=%s actual=%s"
            % (len(texts), len(rows)),
            http_status=502,
        )

    rows = sorted(rows, key=lambda item: item.get("index", 0))
    vectors = np.asarray([item.get("embedding") for item in rows], dtype="float32")

    if vectors.ndim != 2:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "embedding response is not a 2D vector matrix",
            http_status=502,
        )

    if EMBEDDING_NORMALIZE:
        vectors = _l2_normalize(vectors)

    return vectors.astype("float32")


def _embed_texts(texts: List[str]) -> np.ndarray:
    if EMBEDDING_PROVIDER == "sentence_transformers":
        return _embed_via_sentence_transformers(texts)
    if EMBEDDING_PROVIDER == "openai_compatible":
        return _embed_via_openai_compatible(texts)

    raise AppError(
        ERR_INTERNAL_ERROR,
        f"unsupported embedding provider: {EMBEDDING_PROVIDER}",
        http_status=500,
    )


def embed_documents(texts: List[str]) -> np.ndarray:
    if not texts:
        raise ValueError("texts must not be empty")

    payload = [format_document_for_embedding(text) for text in texts]
    return _embed_texts(payload)


def embed_query(text: str) -> np.ndarray:
    if not text or not text.strip():
        raise ValueError("query text must not be empty")

    vector = _embed_texts([format_query_for_embedding(text)])
    return vector[0].astype("float32")
