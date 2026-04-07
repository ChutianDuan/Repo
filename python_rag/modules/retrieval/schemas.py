from typing import List, Optional
from pydantic import BaseModel, Field



class SearchRequest(BaseModel):
    doc_id : int = Field(..., gt=0)
    query : str = Field(..., min_length=1)
    top_k : int = Field(5, ge=1, le=100)


class SearchHit(BaseModel):
    doc_id: int
    chunk_id: int
    chunk_index: int
    score: float
    content: str
    snippet: str

class SearchResponseData(BaseModel):
    doc_id: int
    query: str
    top_k: int
    hits: List[SearchHit]


class SearchResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: SearchResponseData

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


