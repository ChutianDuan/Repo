from typing import List
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