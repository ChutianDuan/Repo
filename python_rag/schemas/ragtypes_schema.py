
from typing import Optional
from pydantic import BaseModel

class RetrievedChunk(BaseModel):
    rank: int
    content: str
    doc_id: int
    chunk_id: Optional[int] = None
    chunk_index: Optional[int]=None
    score: Optional[float] = None

class PromptBuildResult(BaseModel):
    system_instruction: str
    user_prompt:str
    context_text:str
    context_count:int
    mode:str


