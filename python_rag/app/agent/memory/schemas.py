from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MemoryMessage(BaseModel):
    message_id: Optional[int] = Field(default=None, gt=0)
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        if key not in type(self).model_fields:
            raise KeyError(key)
        return getattr(self, key)

    def to_chat_message(self) -> Dict[str, str]:
        return {
            "role": self.role,
            "content": self.content,
        }


class SessionMemory(BaseModel):
    summary: str = ""
    summary_message_id: Optional[int] = Field(default=None, gt=0)
    recent_messages: List[MemoryMessage] = Field(default_factory=list)
    message_count: int = Field(default=0, ge=0)
    summary_task_queued: bool = False
    summary_updated: bool = False


class SessionSummaryTaskPayload(BaseModel):
    session_id: int = Field(..., gt=0)
    current_user_message_id: Optional[int] = Field(default=None, gt=0)
    source_until_message_id: Optional[int] = Field(default=None, gt=0)


class SessionSummaryResult(BaseModel):
    session_id: int = Field(..., gt=0)
    updated: bool = False
    summary_message_id: Optional[int] = Field(default=None, gt=0)
    source_message_count: int = Field(default=0, ge=0)
    reason: Optional[str] = None


__all__ = [
    "MemoryMessage",
    "SessionMemory",
    "SessionSummaryResult",
    "SessionSummaryTaskPayload",
]
