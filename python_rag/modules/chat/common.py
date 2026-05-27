from typing import Any, Dict, List, Optional

from python_rag.modules.llm.mock_service import build_mock_answer


NO_CONTEXT_ANSWER = "根据当前检索内容无法确定该问题的答案，因为没有检索到可用文档片段。"


def retrieve_hits(
    question: str,
    doc_id: Optional[int],
    doc_ids: Optional[List[int]],
    top_k: int,
) -> Dict[str, Any]:
    from python_rag.modules.retrieval.service import search_in_documents

    return search_in_documents(
        query=question,
        doc_id=doc_id,
        doc_ids=doc_ids,
        top_k=top_k,
        track_metric=False,
    ) or {}


def chunk_to_dict(chunk: Any) -> Dict[str, Any]:
    if isinstance(chunk, dict):
        return chunk
    if hasattr(chunk, "__dict__"):
        return dict(chunk.__dict__)
    return {"content": str(chunk)}


def chunks_to_dicts(chunks: List[Any]) -> List[Dict[str, Any]]:
    return [chunk_to_dict(chunk) for chunk in chunks]


def generate_mock_answer(question: str, context_chunks: List[Dict[str, Any]]) -> str:
    return build_mock_answer(
        user_query=question,
        hits=context_chunks,
    )


def normalize_hit_for_citation(hit: Dict[str, Any], rank: int) -> Dict[str, Any]:
    citation_score = hit.get("rerank_score")
    if citation_score is None:
        citation_score = hit.get("score")

    content = hit.get("content") or hit.get("text") or hit.get("chunk_text") or ""
    return {
        "rank": rank,
        "doc_id": hit.get("doc_id"),
        "chunk_id": hit.get("chunk_id") or hit.get("id"),
        "chunk_index": hit.get("chunk_index", hit.get("seq", hit.get("index"))),
        "score": citation_score or 0,
        "faiss_score": hit.get("faiss_score"),
        "bm25_score": hit.get("bm25_score"),
        "rrf_score": hit.get("rrf_score"),
        "rerank_score": hit.get("rerank_score"),
        "faiss_rank": hit.get("faiss_rank"),
        "bm25_rank": hit.get("bm25_rank"),
        "rrf_rank": hit.get("rrf_rank"),
        "original_rank": hit.get("original_rank"),
        "content": content,
        "snippet": (hit.get("snippet") or content)[:300],
    }


def build_citations_from_hits(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_hit_for_citation(hit, rank) for rank, hit in enumerate(hits, start=1)]
