import logging
import time
from typing import Any, Dict, Generator, List, Optional

from python_rag.core.error_codes import ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError

from python_rag.modules.messages.repo import (
    get_message_by_id,
    list_recent_messages_by_session_id,
)
from python_rag.modules.sessions.repo import get_session_by_id

from python_rag.modules.retrieval.service import search_in_document
from python_rag.modules.retrieval.context_assembler import assemble_context

from python_rag.modules.llm.service import LLMServiceError, generate_answer
from python_rag.modules.llm.mock_service import build_mock_answer

from python_rag.modules.chat.stream_event_builder import (
    build_delta_event,
    build_done_event,
    build_error_event,
)
from python_rag.modules.chat.conversation_assembler import ConversationAssembler
from python_rag.modules.chat.prompt_templates import SYSTEM_PROMPT

from python_rag.config import (
    STREAM_DELTA_CHARS,
    STREAM_MOCK_DELAY_MS,
    CHAT_TOP_K,
    CHAT_ENABLE_MOCK_FALLBACK,
)

from python_rag.modules.chat.stream_persistence import persist_stream_result



logger = logging.getLogger(__name__)


class StreamingChatServiceError(Exception):
    pass


def _get_user_message(user_message_id: int) -> Dict[str, Any]:
    message = get_message_by_id(user_message_id)
    if not message:
        raise StreamingChatServiceError("user message not found")
    return message


def _get_session(session_id: int) -> Dict[str, Any]:
    session = get_session_by_id(session_id)
    if not session:
        raise AppError(ERR_INTERNAL_ERROR, "session not found")
    return session


def _safe_get_question_from_message(user_message: Dict[str, Any]) -> str:
    content = user_message.get("content")
    if not content:
        raise StreamingChatServiceError("user message content is empty")
    return str(content).strip()


def _retrieve_hits(question: str, doc_id: int, top_k: int) -> List[Dict[str, Any]]:
    result = search_in_document(
        query=question,
        doc_id=doc_id,
        top_k=top_k,
    )
    if not result:
        return []
    return result.get("hits", [])


def _chunk_to_dict(chunk: Any) -> Dict[str, Any]:
    if isinstance(chunk, dict):
        return chunk
    if hasattr(chunk, "__dict__"):
        return dict(chunk.__dict__)
    return {"content": str(chunk)}


def _chunks_to_dicts(chunks: List[Any]) -> List[Dict[str, Any]]:
    return [_chunk_to_dict(chunk) for chunk in chunks]


def _generate_mock_answer(question: str, context_chunks: List[Dict[str, Any]]) -> str:
    return build_mock_answer(
        user_query=question,
        hits=context_chunks,
    )


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    text = text or ""
    if chunk_size <= 0:
        chunk_size = 20
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def _mock_stream_answer(answer_text: str) -> Generator[str, None, None]:
    chunk_size = STREAM_DELTA_CHARS
    sleep_ms = STREAM_MOCK_DELAY_MS

    pieces = _chunk_text(answer_text, chunk_size)
    for idx, piece in enumerate(pieces, 1):
        yield build_delta_event(piece, idx)
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)


def _build_prompt_preview(messages: List[Dict[str, str]], max_chars: int = 4000) -> str:
    lines = []
    for i, msg in enumerate(messages, start=1):
        role = msg.get("role", "")
        content = (msg.get("content") or "").replace("\n", "\\n")
        if len(content) > 300:
            content = content[:300] + "...(truncated)"
        lines.append(f"[{i}] role={role} content={content}")
    preview = "\n".join(lines)
    if len(preview) > max_chars:
        preview = preview[:max_chars] + "\n...(prompt preview truncated)"
    return preview


def stream_chat_for_message(
    session_id: int,
    doc_id: int,
    user_message_id: int,
    top_k: Optional[int] = None,
) -> Generator[str, None, None]:
    top_k = top_k or CHAT_TOP_K

    try:
        _get_session(session_id)

        user_message = _get_user_message(user_message_id)
        if user_message.get("session_id") != session_id:
            raise AppError(ERR_INTERNAL_ERROR, "user message does not belong to session")

        question = _safe_get_question_from_message(user_message)

        raw_hits = _retrieve_hits(
            question=question,
            doc_id=doc_id,
            top_k=top_k,
        )
        chunks, context_mode = assemble_context(raw_hits)
        chunk_dicts = _chunks_to_dicts(chunks)

        # 新增：读取最近消息
        history_messages = list_recent_messages_by_session_id(
            session_id=session_id,
            limit=10,
        )

        # 新增：组装多轮上下文
        assembler = ConversationAssembler(max_rounds=3)
        messages = assembler.build_messages(
            system_prompt=SYSTEM_PROMPT,
            history_messages=history_messages,
            retrieved_chunks=chunk_dicts,
            current_question=question,
            current_user_message_id=user_message_id,
        )

        logger.info(
            "stream chat start session_id=%s doc_id=%s user_message_id=%s retrieved_count=%s mode=%s",
            session_id,
            doc_id,
            user_message_id,
            len(chunks),
            context_mode,
        )
        logger.info(
            "stream chat prompt preview session_id=%s user_message_id=%s\n%s",
            session_id,
            user_message_id,
            _build_prompt_preview(messages),
        )

        if context_mode == "no_context":
            answer_text = "根据当前检索内容无法确定该问题的答案，因为没有检索到可用文档片段。"
            answer_source = "no_context"
        else:
            try:
                llm_result = generate_answer(
                    question=question,
                    chunks=chunk_dicts,
                    messages=messages,
                )
                answer_text = llm_result["answer"]
                answer_source = "llm"
            except LLMServiceError:
                if CHAT_ENABLE_MOCK_FALLBACK:
                    answer_text = _generate_mock_answer(
                        question=question,
                        context_chunks=chunk_dicts,
                    )
                    answer_source = "mock_fallback"
                else:
                    raise

        for event_text in _mock_stream_answer(answer_text):
            yield event_text
            
        assistant_message = persist_stream_result(
            session_id=session_id,
            answer_text=answer_text,
            retrieval_hits=chunk_dicts,
            answer_source=answer_source,
            context_mode=context_mode,
        )


        yield build_done_event(
            {
                "assistant_message_id": assistant_message["message_id"],
                "answer_source": answer_source,
                "context_mode": context_mode,
                "retrieved_count": len(chunks),
            }
        )

    except Exception as e:
        logger.exception(
            "stream chat failed session_id=%s doc_id=%s user_message_id=%s",
            session_id,
            doc_id,
            user_message_id,
        )
        yield build_error_event(str(e))