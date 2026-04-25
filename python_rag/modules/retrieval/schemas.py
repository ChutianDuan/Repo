from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field



class SearchRequest(BaseModel):
    doc_id : int = Field(..., gt=0)
    query : str = Field(..., min_length=1)
    top_k : int = Field(5, ge=1, le=100)


class SearchHit(BaseModel):
    doc_id: int
    chunk_id: int
    chunk_index: int
    rank: Optional[int] = None
    score: float
    faiss_score: Optional[float] = None
    rerank_score: Optional[float] = None
    original_rank: Optional[int] = None
    content: str
    snippet: str


class SearchMetrics(BaseModel):
    embedding_ms: int | None = None
    faiss_ms: int | None = None
    rerank_ms: int | None = None
    retrieval_ms: int | None = None
    candidate_top_k: int | None = None
    final_top_k: int | None = None
    rerank: Optional[Dict[str, Any]] = None

class SearchResponseData(BaseModel):
    doc_id: int
    query: str
    top_k: int
    candidate_top_k: Optional[int] = None
    hits: List[SearchHit]
    metrics: SearchMetrics | None = None


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
    faiss_score: Optional[float] = None
    rerank_score: Optional[float] = None
    original_rank: Optional[int] = None

class PromptBuildResult(BaseModel):
    system_instruction: str
    user_prompt:str
    context_text:str
    context_count:int
    mode:str
