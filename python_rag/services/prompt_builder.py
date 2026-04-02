from typing import Any, Dict, List, Optional
from python_rag.config import CHAT_MAX_CHUNK_CHARS

SYSTEM_INSTRUCTION = (
    "你是一个RAG问答助手。\n"
    "请严格基于提供的检索内容回答问题。\n"
    "如果答案无法从检索内容中得到，请明确说明："
    "“根据当前检索内容无法确定”。\n"
    "不要编造未在检索内容中出现的事实。\n"
    "回答要简洁、准确、有条理。\n"
    "当检索内容中存在多个片段时，请优先整合共同信息。"
)

def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_chunk(raw_chunk: Dict[str, Any], idx: int) -> Dict[str, Any]:
    text = _safe_text(raw_chunk.get("text") or raw_chunk.get("content"))
    if len(text) > CHAT_MAX_CHUNK_CHARS:
        text = text[:CHAT_MAX_CHUNK_CHARS] + "..."
    return {
        "rank": idx + 1,
        "chunk_id": raw_chunk.get("chunk_id") or raw_chunk.get("id"),
        "doc_id": raw_chunk.get("doc_id"),
        "chunk_index": (
            raw_chunk.get("chunk_index")
            if raw_chunk.get("chunk_index") is not None
            else raw_chunk.get("seq", raw_chunk.get("index"))
        ),
        "score": raw_chunk.get("score"),
        "content": text,
    }

def normalize_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(chunks):
        normalized.append(normalize_chunk(item, idx))
    return normalized


def build_context_text(chunks: List[Dict[str, Any]]) -> str:
    normalized = normalize_chunks(chunks)
    parts = []

    for chunk in normalized:
        header_parts = ["[Chunk %d]" % chunk["rank"]]
        if chunk.get("doc_id") is not None:
            header_parts.append("doc_id=%s" % chunk["doc_id"])
        if chunk.get("chunk_index") is not None:
            header_parts.append("chunk_index=%s" % chunk["chunk_index"])
        if chunk.get("score") is not None:
            try:
                header_parts.append("score=%.4f" % float(chunk["score"]))
            except Exception:
                header_parts.append("score=%s" % chunk["score"])

        header = " | ".join(header_parts)
        parts.append(header)
        parts.append(chunk["content"])
        parts.append("")

    return "\n".join(parts).strip()

def build_user_prompt(question: str, chunks: List[Dict[str, Any]]) -> str:
    context_text = build_context_text(chunks)
    prompt = (
        "已检索内容：\n\n"
        "%s\n\n"
        "用户问题：\n"
        "%s\n\n"
        "请基于以上检索内容作答。若无法确定，请明确说明无法确定。"
    ) % (context_text, question.strip())
    return prompt
def build_no_context_user_prompt(question: str) -> str:
    prompt = (
        "当前没有检索到可用文档片段。\n\n"
        "用户问题：\n"
        "%s\n\n"
        "请不要编造答案。请明确说明根据当前检索内容无法确定。"
    ) % question.strip()
    return prompt


def build_messages(
    question: str,
    chunks: List[Dict[str, Any]],
    system_instruction: Optional[str] = None,
) -> List[Dict[str, str]]:
    sys_msg = system_instruction or SYSTEM_INSTRUCTION

    if chunks:
        user_msg = build_user_prompt(question, chunks)
    else:
        user_msg = build_no_context_user_prompt(question)

    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user_msg},
    ]
