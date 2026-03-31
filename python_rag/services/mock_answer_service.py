

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