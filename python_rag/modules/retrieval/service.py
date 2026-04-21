
from python_rag.core.error_codes import ERR_INDEX_NOT_FOUND, ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError
from python_rag.core.logger import logger


from python_rag.modules.documents.repo import get_document_index_by_doc_id
from python_rag.modules.ingest.embedding_service import (
    embed_query,
    get_embedding_model_name,
)
from python_rag.modules.retrieval.faiss_service import search_doc_faiss_index


def _build_snippet(text, max_len=180):
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def search_in_document(doc_id, query, top_k=3):
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

    hits = search_doc_faiss_index(
        index_path=index_meta["index_path"],
        mapping_path=index_meta["mapping_path"],
        query_vector=query_vector,
        top_k=top_k,
    )

    result_hits = []
    for item in hits:
        content = item.get("content", "")
        result_hits.append(
            {
                "doc_id": item["doc_id"],
                "chunk_id": item["chunk_id"],
                "chunk_index": item["chunk_index"],
                "score": round(float(item["score"]), 6),
                "content": content,
                "snippet": _build_snippet(content),
            }
        )

    return {
        "doc_id": doc_id,
        "query": query,
        "top_k": top_k,
        "hits": result_hits,
    }
