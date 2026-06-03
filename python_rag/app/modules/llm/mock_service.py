from typing import Any, Dict, List


def build_mock_answer(user_query, hits):
    """
    Day 5 mock answer:
    - 不调用 LLM
    - 直接基于 retrieval hits 做模板拼接
    """
    if not hits:
        return (
            f"我没有在当前文档中检索到与问题“{user_query}”高度相关的内容。"
            "你可以尝试换一个更具体的问法。"
        )

    lines = []
    lines.append(f"针对你的问题“{user_query}”，我从文档中检索到了以下相关内容：")

    for i, item in enumerate(hits, 1):
        snippet = (item.get("snippet") or item.get("content") or "").strip()
        lines.append(
            f"{i}. [chunk_index={item['chunk_index']}, score={item['score']}] {snippet}"
        )

    lines.append("以上是基于当前文档检索结果生成的 mock answer，下一步可以接入真实 LLM 总结这些片段。")
    return "\n".join(lines)


def generate_mock_answer(question: str, context_chunks: List[Dict[str, Any]]) -> str:
    if not context_chunks:
        return (
            "根据当前检索内容无法确定该问题的答案。"
            "当前没有检索到可直接支持回答的文档片段。"
        )

    lines = []
    lines.append("基于当前检索到的文档内容，给出如下简要回答：")
    lines.append("")
    lines.append("问题：%s" % question.strip())
    lines.append("")
    lines.append("参考片段摘要：")

    for idx, chunk in enumerate(context_chunks[:3], 1):
        text = (
            chunk.get("content")
            or chunk.get("text")
            or chunk.get("chunk_text")
            or ""
        ).strip()
        if len(text) > 200:
            text = text[:200] + " ..."
        lines.append("%d. %s" % (idx, text))

    lines.append("")
    lines.append("说明：当前回答来自 mock fallback，用于在 LLM 不可用时保证链路可用。")
    return "\n".join(lines)