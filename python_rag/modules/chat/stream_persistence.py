from typing import Any, Dict, List

from python_rag.modules.messages.repo import create_message
from python_rag.modules.chat.repo import bulk_insert_citations


def _normalize_hit_for_citation(hit: Dict[str, Any], rank: int) -> Dict[str, Any]:
    return {
        "doc_id": hit.get("doc_id"),
        "chunk_id": hit.get("chunk_id"),
        "chunk_index": hit.get("chunk_index"),
        "score": hit.get("score") or 0,
        "content": hit.get("content"),
        "snippet": (hit.get("snippet") or hit.get("content") or "")[:300],
        "rank": rank,
    }


def persist_stream_result(
    session_id: int,
    answer_text: str,
    retrieval_hits: List[Dict[str, Any]],
    answer_source: str,
    context_mode: str,
) -> Dict[str, Any]:
    """
    在 stream done 前调用：
    1. 保存 assistant message
    2. 保存 citations
    3. 返回 assistant message 信息
    """

    assistant_message = create_message(
        session_id=session_id,
        role="assistant",
        content=answer_text,
        status="SUCCESS",
        meta_json={
            "answer_source": answer_source,
            "context_mode": context_mode,
            "retrieved_count": len(retrieval_hits),
        },
    )

    citation_rows = []
    for idx, hit in enumerate(retrieval_hits, start=1):
        citation_rows.append(
            _normalize_hit_for_citation(hit, idx)
        )

    if citation_rows:
        bulk_insert_citations(
            message_id=assistant_message["message_id"],
            hits=citation_rows,
        )

    return assistant_message
