from pydantic import BaseModel, Field
from typing import Optional, List, Dict

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