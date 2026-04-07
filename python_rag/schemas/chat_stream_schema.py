
from typing import Optional
from pydantic import BaseModel

class ChatStreamRequest(BaseModel):
    session_id: int
    doc_id: int
    user_message_id: int
    top_k: Optional[int] = 3