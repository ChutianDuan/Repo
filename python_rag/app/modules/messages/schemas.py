from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from python_rag.app.shared.schemas import ApiResponse


class CreateMessageRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=32)
    content: str = Field(..., min_length=1)
    status: str = Field(default="SUCCESS", max_length=32)


class UpdateMessageStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=32)


class CitationItem(BaseModel):
    citation_id: Optional[int] = None
    doc_id: int
    chunk_id: int
    chunk_index: int
    score: float
    snippet: str = ""
    created_at: Optional[str] = None


class MessageItem(BaseModel):
    message_id: int
    session_id: int
    role: str
    content: str
    status: str
    citations: List[CitationItem] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: Optional[str] = None


class CreateMessageResponse(ApiResponse):
    data: MessageItem


class UpdateMessageStatusResponse(ApiResponse):
    data: MessageItem


class ListMessagesResponseData(BaseModel):
    session_id: int
    items: List[MessageItem]


class ListMessagesResponse(ApiResponse):
    data: ListMessagesResponseData
