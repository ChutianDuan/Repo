from typing import Any, Dict, List, Tuple

from python_rag.schemas.ragtypes_schema import RetrievedChunk
from python_rag.config import CHAT_MAX_CHUNK_CHARS, CHAT_TOP_K, CHAT_MIN_RETRIEVAL_SCORE


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_raw_hit(raw_hit: Dict[str, Any], rank: int) -> RetrievedChunk:
    text = (
        raw_hit.get("content")
        or raw_hit.get("text")
        or raw_hit.get("chunk_text")
        or ""
    )
    text = _safe_text(text)

    if len(text) > CHAT_MAX_CHUNK_CHARS:
        text = text[:CHAT_MAX_CHUNK_CHARS] + " ..."

    score = raw_hit.get("score")
    try:
        score = float(score) if score is not None else None
    except Exception:
        score = None

    return RetrievedChunk(
        rank=rank,
        content=text,
        doc_id=raw_hit.get("doc_id"),
        chunk_id=raw_hit.get("chunk_id") or raw_hit.get("id"),
        chunk_index=raw_hit.get("chunk_index", raw_hit.get("seq", raw_hit.get("index"))),
        score=score,
    )


def normalize_hits(raw_hits: List[Dict[str, Any]]) -> List[RetrievedChunk]:
    chunks: List[RetrievedChunk] = []
    for idx, raw_hit in enumerate(raw_hits, 1):
        chunk = normalize_raw_hit(raw_hit=raw_hit, rank=idx)
        if chunk.content:
            chunks.append(chunk)
    return chunks


def deduplicate_chunks(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    seen = set()
    result: List[RetrievedChunk] = []

    for chunk in chunks:
        key = chunk.content
        if key in seen:
            continue
        seen.add(key)
        result.append(chunk)

    return result


def rerank_sequentially(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    result: List[RetrievedChunk] = []
    for idx, chunk in enumerate(chunks, 1):
        result.append(
            RetrievedChunk(
                rank=idx,
                content=chunk.content,
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                score=chunk.score,
            )
        )
    return result


def detect_context_mode(chunks: List[RetrievedChunk]) -> str:
    if not chunks:
        return "no_context"

    first_score = chunks[0].score
    if first_score is not None:
        min_score = CHAT_MIN_RETRIEVAL_SCORE
        if min_score is not None and first_score < min_score:
            return "low_confidence"

    return "normal"


def assemble_context(raw_hits: List[Dict[str, Any]]) -> Tuple[List[RetrievedChunk], str]:
    chunks = normalize_hits(raw_hits)
    chunks = deduplicate_chunks(chunks)
    chunks = chunks[:CHAT_TOP_K]
    chunks = rerank_sequentially(chunks)
    mode = detect_context_mode(chunks)
    return chunks, mode


if __name__ == "__main__":
    raw_hits = [
        {"text": "A 文本", "score": 0.91, "doc_id": 1, "index": 0},
        {"content": "A 文本", "score": 0.89, "doc_id": 1, "index": 1},
        {"content": "B 文本", "score": 0.85, "doc_id": 1, "index": 2},
        {"content": "   ", "score": 0.50, "doc_id": 1, "index": 3},
    ]

    chunks, mode = assemble_context(raw_hits)
    print(chunks)
    print(mode)