from typing import List

import numpy as np
import torch

from python_rag.core.error_codes import ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

_model = None


def get_model():
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
            _model = SentenceTransformer(MODEL_NAME, device=DEVICE)
        except Exception as exc:
            raise AppError(
                ERR_INTERNAL_ERROR,
                f"failed to initialize embedding model '{MODEL_NAME}': {exc}",
                http_status=500,
            ) from exc
    return _model


def embed_documents(texts: List[str]) -> np.ndarray:
    if not texts:
        raise ValueError("texts must not be empty")
    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embeddings.astype("float32")


def embed_query(text: str) -> np.ndarray:
    if not text or not text.strip():
        raise ValueError("query text must not be empty")
    model = get_model()
    embedding = model.encode(
        [text],
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embedding[0].astype("float32")
