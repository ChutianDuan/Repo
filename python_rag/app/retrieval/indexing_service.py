from typing import Any, Dict, Iterable, List, Optional

from python_rag.app.core.config import VECTOR_STORE_PROVIDER
from python_rag.app.core.error_codes import ERR_INTERNAL_ERROR
from python_rag.app.core.errors import AppError
from python_rag.app.retrieval.vector_store.base import VectorRecord
from python_rag.app.retrieval.vector_store.lancedb_store import LanceDBVectorStore
from python_rag.app.shared.hash_utils import sha256_bytes


VECTOR_STATUS_INDEXED = "indexed"


def get_vector_store(provider: Optional[str] = None):
    selected = (provider or VECTOR_STORE_PROVIDER or "lancedb").strip().lower()
    if selected == "lancedb":
        return LanceDBVectorStore()
    raise AppError(
        ERR_INTERNAL_ERROR,
        "unsupported vector store provider: {0}".format(selected),
        http_status=500,
    )


def _normalize_vector(vector: Any) -> List[float]:
    try:
        import numpy as np
    except Exception as exc:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "numpy dependency is not available for indexing vectors: {0}".format(exc),
            http_status=500,
        ) from exc
    array = np.asarray(vector, dtype="float32").reshape(-1)
    return [float(item) for item in array]


def build_vector_records(document: Dict[str, Any], chunk_rows: List[Dict[str, Any]], vectors: Any) -> List[VectorRecord]:
    try:
        import numpy as np
    except Exception as exc:
        raise AppError(
            ERR_INTERNAL_ERROR,
            "numpy dependency is not available for indexing vectors: {0}".format(exc),
            http_status=500,
        ) from exc

    vectors_array = np.asarray(vectors, dtype="float32")
    if vectors_array.ndim != 2 or vectors_array.shape[0] != len(chunk_rows):
        raise ValueError("chunk count and vector count mismatch")

    records = []
    for index, chunk in enumerate(chunk_rows):
        content = chunk.get("content") or chunk.get("text") or ""
        records.append(
            VectorRecord(
                chunk_id=int(chunk["id"]),
                document_id=int(chunk.get("doc_id") or document["id"]),
                chunk_index=int(chunk["chunk_index"]),
                title=document.get("filename") or "",
                content_hash=sha256_bytes(str(content).encode("utf-8")),
                status=VECTOR_STATUS_INDEXED,
                vector=_normalize_vector(vectors_array[index]),
            )
        )
    return records


def upsert_document_chunk_vectors(
    document: Dict[str, Any],
    chunk_rows: List[Dict[str, Any]],
    vectors: Any,
    *,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    records = build_vector_records(document=document, chunk_rows=chunk_rows, vectors=vectors)
    meta = get_vector_store(provider).upsert(records)
    meta["provider"] = provider or VECTOR_STORE_PROVIDER
    return meta


def delete_document_vectors(document_id: int, *, provider: Optional[str] = None) -> int:
    return get_vector_store(provider).delete_document(int(document_id))


def search_vectors(
    query_vector: Any,
    *,
    top_k: int,
    document_ids: Optional[Iterable[int]] = None,
    provider: Optional[str] = None,
):
    return get_vector_store(provider).search(
        query_vector=query_vector,
        top_k=top_k,
        document_ids=document_ids,
    )
