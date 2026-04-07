from pydantic import BaseModel, Field
from typing import Optional

class SubmitChatJobRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    doc_id: int = Field(..., gt=0)
    user_message_id: int = Field(..., gt=0)
    top_k: int = Field(3, ge=1, le=10)


class ChatStreamRequest(BaseModel):
    session_id: int
    doc_id: int
    user_message_id: int
    top_k: Optional[int] = 3