import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from python_rag.modules.llm import service as llm_service
from python_rag.modules.messages.repo import list_messages_by_session_id
from python_rag.modules.sessions.repo import get_session_by_id, update_session_summary


logger = logging.getLogger(__name__)

RECENT_MEMORY_LIMIT = 8
SUMMARY_TRIGGER_MESSAGE_COUNT = 12
SESSION_SUMMARY_HEADER = "[会话摘要 / 中期记忆]"
RECENT_MEMORY_HEADER = "[最近对话 / 短期记忆]"
MAX_MEMORY_MESSAGES_LOAD = 500

_ROLE_LABELS = {
    "user": "用户",
    "assistant": "助手",
}


@dataclass
class SessionMemory:
    summary: str = ""
    recent_messages: List[Dict[str, str]] = field(default_factory=list)
    message_count: int = 0
    summary_updated: bool = False


def _same_message_id(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return str(left) == str(right)


def _clean_memory_messages(
    messages: List[Dict[str, Any]],
    current_user_message_id: Optional[int] = None,
) -> List[Dict[str, str]]:
    cleaned: List[Dict[str, str]] = []
    for message in messages:
        if _same_message_id(message.get("message_id"), current_user_message_id):
            continue

        role = str(message.get("role") or "").strip()
        if role not in ("user", "assistant"):
            continue

        content = str(message.get("content") or "").strip()
        if not content:
            continue

        status = message.get("status")
        if role == "assistant" and status not in (None, "SUCCESS", "success"):
            continue

        cleaned.append({"role": role, "content": content})
    return cleaned


def _format_messages(messages: List[Dict[str, str]]) -> str:
    lines = []
    for index, message in enumerate(messages, start=1):
        role = _ROLE_LABELS.get(message.get("role"), str(message.get("role") or ""))
        content = str(message.get("content") or "").replace("\n", " ").strip()
        if content:
            lines.append("{0}. {1}: {2}".format(index, role, content))
    return "\n".join(lines)


def build_summary_messages(
    existing_summary: str,
    source_messages: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    parts = [
        "请把旧会话消息压缩成 session summary，供后续 Agent 作为中期记忆使用。",
        "要求：保留用户目标、关键约束、已确认事实、已给出的结论和未完成事项；忽略寒暄和重复内容；使用简洁中文，最多 300 字。",
    ]
    existing_summary = str(existing_summary or "").strip()
    if existing_summary:
        parts.append("已有 session summary：\n" + existing_summary)
    parts.append("需要压缩的旧 messages：\n" + _format_messages(source_messages))

    return [
        {
            "role": "system",
            "content": "你负责维护会话摘要，只输出更新后的 summary，不要输出解释。",
        },
        {
            "role": "user",
            "content": "\n\n".join(parts),
        },
    ]


def summarize_messages(
    existing_summary: str,
    source_messages: List[Dict[str, str]],
) -> str:
    if not source_messages:
        return str(existing_summary or "").strip()

    result = llm_service.generate_from_messages(
        build_summary_messages(
            existing_summary=existing_summary,
            source_messages=source_messages,
        )
    )
    message = result.get("message") or {}
    summary = str(result.get("answer") or message.get("content") or "").strip()
    return summary or str(existing_summary or "").strip()


def build_session_summary_context(summary: str) -> str:
    summary = str(summary or "").strip()
    if not summary:
        return ""
    return SESSION_SUMMARY_HEADER + "\n" + summary


def format_memory_debug_context(memory: SessionMemory) -> str:
    parts = []
    summary_context = build_session_summary_context(memory.summary)
    if summary_context:
        parts.append(summary_context)
    if memory.recent_messages:
        parts.append(RECENT_MEMORY_HEADER + "\n" + _format_messages(memory.recent_messages))
    return "\n\n".join(parts)


def load_session_memory(
    session_id: Optional[int],
    current_user_message_id: Optional[int] = None,
) -> SessionMemory:
    if session_id is None:
        return SessionMemory()

    session = get_session_by_id(session_id) or {}
    summary = str(session.get("summary") or "").strip()
    messages = list_messages_by_session_id(
        session_id=session_id,
        limit=MAX_MEMORY_MESSAGES_LOAD,
    )
    cleaned = _clean_memory_messages(
        messages=messages,
        current_user_message_id=current_user_message_id,
    )

    summary_updated = False
    if len(messages) > SUMMARY_TRIGGER_MESSAGE_COUNT:
        source_messages = cleaned[:-RECENT_MEMORY_LIMIT]
        if source_messages:
            try:
                next_summary = summarize_messages(
                    existing_summary=summary,
                    source_messages=source_messages,
                )
            except Exception:
                logger.exception(
                    "agent session summary generation failed session_id=%s",
                    session_id,
                )
            else:
                if next_summary and next_summary != summary:
                    update_session_summary(session_id=session_id, summary=next_summary)
                    summary = next_summary
                    summary_updated = True

    return SessionMemory(
        summary=summary,
        recent_messages=cleaned[-RECENT_MEMORY_LIMIT:],
        message_count=len(messages),
        summary_updated=summary_updated,
    )


__all__ = [
    "RECENT_MEMORY_LIMIT",
    "SUMMARY_TRIGGER_MESSAGE_COUNT",
    "SESSION_SUMMARY_HEADER",
    "SessionMemory",
    "build_session_summary_context",
    "build_summary_messages",
    "format_memory_debug_context",
    "load_session_memory",
    "summarize_messages",
]
