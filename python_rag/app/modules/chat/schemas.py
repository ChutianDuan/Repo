from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from python_rag.app.shared.validators import normalize_positive_int_list


class SubmitChatJobRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    doc_id: Optional[int] = Field(default=None, gt=0)
    doc_ids: Optional[List[int]] = Field(default=None, min_length=1, max_length=100)
    user_message_id: int = Field(..., gt=0)
    top_k: int = Field(3, ge=1, le=10)

    @field_validator("doc_ids")
    @classmethod
    def validate_doc_ids(cls, value):
        return normalize_positive_int_list(value, "doc_ids")


class ChatStreamRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    doc_id: Optional[int] = Field(default=None, gt=0)
    doc_ids: Optional[List[int]] = Field(default=None, min_length=1, max_length=100)
    user_message_id: int = Field(..., gt=0)
    top_k: Optional[int] = Field(3, ge=1, le=10)

    @field_validator("doc_ids")
    @classmethod
    def validate_doc_ids(cls, value):
        return normalize_positive_int_list(value, "doc_ids")


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
