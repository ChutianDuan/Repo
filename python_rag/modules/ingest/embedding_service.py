from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
import torch


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# 后期优化自动选者GPU 均衡负载
device = "cpu" if torch.cuda.is_available() else "cpu"

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, device=device)
    return _model

def embed_documents(texts: List[str]) -> np.ndarray:
    model = get_model()
    embeddings = model.encode(texts, batch_size=32,
        show_progress_bar=False,convert_to_numpy=True,normalize_embeddings=True,)
    return embeddings.astype("float32")

def embed_query(text: str) -> np.ndarray:
    model = get_model()
    embedding = model.encode([text], show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True,)
    return embedding[0].astype("float32")