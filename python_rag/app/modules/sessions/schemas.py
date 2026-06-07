from typing import Optional

from pydantic import BaseModel, Field

from python_rag.app.modules.messages.schemas import (
    CitationItem,
    CreateMessageRequest,
    CreateMessageResponse,
    ListMessagesResponse,
    ListMessagesResponseData,
    MessageItem,
    UpdateMessageStatusRequest,
    UpdateMessageStatusResponse,
)
from python_rag.app.shared.schemas import ApiResponse


class CreateSessionRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    title: Optional[str] = Field(default="New Session", max_length=255)


class SessionItem(BaseModel):
    session_id: int
    user_id: int
    title: str
    created_at: str


class CreateSessionResponse(ApiResponse):
    data: SessionItem


__all__ = [
    "CitationItem",
    "CreateMessageRequest",
    "CreateMessageResponse",
    "CreateSessionRequest",
    "CreateSessionResponse",
    "ListMessagesResponse",
    "ListMessagesResponseData",
    "MessageItem",
    "SessionItem",
    "UpdateMessageStatusRequest",
    "UpdateMessageStatusResponse",
]
