from typing import Optional, List, Dict

from pydantic import BaseModel, Field, field_validator


def _normalize_doc_ids(value):
    if value is None:
        return value
    normalized = []
    seen = set()
    for item in value:
        doc_id = int(item)
        if doc_id <= 0:
            raise ValueError("doc_ids must contain positive integers")
        if doc_id in seen:
            continue
        seen.add(doc_id)
        normalized.append(doc_id)
    if not normalized:
        raise ValueError("doc_ids must not be empty")
    return normalized


class SubmitChatJobRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    doc_id: Optional[int] = Field(default=None, gt=0)
    doc_ids: Optional[List[int]] = Field(default=None, min_length=1, max_length=100)
    user_message_id: int = Field(..., gt=0)
    top_k: int = Field(3, ge=1, le=10)

    @field_validator("doc_ids")
    @classmethod
    def validate_doc_ids(cls, value):
        return _normalize_doc_ids(value)


class ChatStreamRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    doc_id: Optional[int] = Field(default=None, gt=0)
    doc_ids: Optional[List[int]] = Field(default=None, min_length=1, max_length=100)
    user_message_id: int = Field(..., gt=0)
    top_k: Optional[int] = Field(3, ge=1, le=10)

    @field_validator("doc_ids")
    @classmethod
    def validate_doc_ids(cls, value):
        return _normalize_doc_ids(value)


class ChatContextInput:
    def __init__(
        self,
        session_id: int,
        history_messages: List[Dict],
        retrieved_chunks: List[str],
        current_question: str,
    ):
        self.session_id = session_id
        self.history_messages = history_messages
        self.retrieved_chunks = retrieved_chunks
        self.current_question = current_question


class ChatContextOutput:
    def __init__(self, messages: List[Dict]):
        self.messages = messages
