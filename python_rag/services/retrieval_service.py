
from python_rag.domain.constants.error_code import NOT_FOUND_ERROR, INTERNAL_ERROR
from python_rag.domain.exceptions import AppException
from python_rag.domain.logger import logger


from python_rag.repos.document_index_repo import get_document_index_by_doc_id
from python_rag.services.embedding_service import embed_query
from python_rag.services.faiss_index_service import search_doc_faiss_index


def _build_snippet(text, max_len=180):
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def search_in_document(doc_id, query, top_k=3):
    index_meta = get_document_index_by_doc_id(doc_id)
    if not index_meta:
        raise AppException(NOT_FOUND_ERROR, "document index not found")

    if index_meta["status"] != "READY":
        raise AppException(INTERNAL_ERROR, "document index is not ready")

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