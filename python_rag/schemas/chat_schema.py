from pydantic import BaseModel, Field

class SubmitChatJobRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    doc_id: int = Field(..., gt=0)
    user_message_id: int = Field(..., gt=0)
    top_k: int = Field(3, ge=1, le=10)