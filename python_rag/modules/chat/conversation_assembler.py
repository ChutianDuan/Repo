from typing import Any, Dict, List, Optional


class ConversationAssembler:
    """system prompt + recent history + retrieval + current question"""

    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds
        self.max_history_messages = max_rounds * 2

    def build_messages(
        self,
        system_prompt: str,
        history_messages: List[Dict[str, Any]],
        retrieved_chunks: List[Dict[str, Any]],
        current_question: str,
        current_user_message_id: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []

        messages.append({
            "role": "system",
            "content": system_prompt,
        })

        recent_history = self._get_recent_history(
            history_messages=history_messages,
            current_question=current_question,
            current_user_message_id=current_user_message_id,
        )
        messages.extend(recent_history)

        retrieval_text = self._format_retrieval(retrieved_chunks)
        if retrieval_text:
            messages.append({
                "role": "system",
                "content": retrieval_text,
            })

        messages.append({
            "role": "user",
            "content": current_question,
        })

        return messages

    def _get_recent_history(
        self,
        history_messages: List[Dict[str, Any]],
        current_question: str,
        current_user_message_id: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        if not history_messages:
            return []

        cleaned: List[Dict[str, str]] = []

        for msg in history_messages:
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            status = msg.get("status")
            message_id = msg.get("message_id")

            if role not in ("user", "assistant"):
                continue
            if not content:
                continue

            # assistant 失败态先不进 prompt
            if role == "assistant" and status not in (None, "SUCCESS", "success"):
                continue

            # 避免当前问题重复进入 history
            if current_user_message_id is not None and message_id == current_user_message_id:
                continue

            # 兜底：按内容去一次重
            if role == "user" and content == current_question:
                continue

            cleaned.append({
                "role": role,
                "content": content,
            })

        return cleaned[-self.max_history_messages:]

    def _format_retrieval(self, chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return ""

        parts = []
        for i, chunk in enumerate(chunks, start=1):
            content = (chunk.get("content") or "").strip()
            if not content:
                continue

            meta = []
            if chunk.get("doc_id") is not None:
                meta.append(f"doc_id={chunk['doc_id']}")
            if chunk.get("chunk_index") is not None:
                meta.append(f"chunk_index={chunk['chunk_index']}")
            if chunk.get("score") is not None:
                try:
                    meta.append(f"score={float(chunk['score']):.4f}")
                except Exception:
                    meta.append(f"score={chunk['score']}")
            if chunk.get("rerank_score") is not None:
                try:
                    meta.append(f"rerank_score={float(chunk['rerank_score']):.4f}")
                except Exception:
                    meta.append(f"rerank_score={chunk['rerank_score']}")
            if chunk.get("original_rank") is not None:
                meta.append(f"original_rank={chunk['original_rank']}")

            header = f"[Chunk {i}]"
            if meta:
                header += " | " + " | ".join(meta)

            parts.append(f"{header}\n{content}")

        if not parts:
            return ""

        return "已检索内容：\n\n" + "\n\n".join(parts)
