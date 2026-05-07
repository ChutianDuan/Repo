from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator



class SearchRequest(BaseModel):
    doc_id : Optional[int] = Field(default=None, gt=0)
    doc_ids: Optional[List[int]] = Field(default=None, min_length=1, max_length=100)
    user_id: Optional[int] = Field(default=None, gt=0)
    query : str = Field(..., min_length=1)
    top_k : int = Field(5, ge=1, le=100)
    relevant_chunk_ids: Optional[List[int]] = None
    relevant_chunk_indexes: Optional[List[int]] = None

    @field_validator("doc_ids")
    @classmethod
    def validate_doc_ids(cls, value):
        if value is None:
            return value
        normalized = []
        seen = set()
        for item in value:
            doc_id = int(item)
            if doc_id <= 0:
                raise ValueError("doc_ids must contain positive integers")
            if doc_id in seen:
                continue
            seen.add(doc_id)
            normalized.append(doc_id)
        if not normalized:
            raise ValueError("doc_ids must not be empty")
        return normalized


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
    doc_faiss_ms: Optional[Dict[str, int]] = None
    rerank_ms: int | None = None
    retrieval_ms: int | None = None
    candidate_top_k: int | None = None
    final_top_k: int | None = None
    rerank: Optional[Dict[str, Any]] = None
    recall_at_k: float | None = None
    mrr: float | None = None
    ndcg: float | None = None
    relevant_count: int | None = None

class SearchResponseData(BaseModel):
    doc_id: Optional[int] = None
    doc_ids: List[int] = Field(default_factory=list)
    doc_count: int = 0
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
