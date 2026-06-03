from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from python_rag.app.shared.validators import normalize_positive_int_list


class SearchRequest(BaseModel):
    doc_id: Optional[int] = Field(default=None, gt=0)
    doc_ids: Optional[List[int]] = Field(default=None, min_length=1, max_length=100)
    user_id: Optional[int] = Field(default=None, gt=0)
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=100)
    relevant_chunk_ids: Optional[List[int]] = None
    relevant_chunk_indexes: Optional[List[int]] = None

    @field_validator("doc_ids")
    @classmethod
    def validate_doc_ids(cls, value):
        return normalize_positive_int_list(value, "doc_ids")


class SearchHit(BaseModel):
    doc_id: int
    chunk_id: int
    chunk_index: int
    rank: Optional[int] = None
    score: float
    faiss_score: Optional[float] = None
    bm25_score: Optional[float] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None
    faiss_rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    rrf_rank: Optional[int] = None
    original_rank: Optional[int] = None
    content: str
    snippet: str


class SearchMetrics(BaseModel):
    embedding_ms: int | None = None
    faiss_ms: int | None = None
    bm25_ms: int | None = None
    rrf_ms: int | None = None
    doc_faiss_ms: Optional[Dict[str, int]] = None
    doc_bm25_ms: Optional[Dict[str, int]] = None
    rerank_ms: int | None = None
    retrieval_ms: int | None = None
    candidate_top_k: int | None = None
    final_top_k: int | None = None
    recall_provider: Optional[str] = None
    candidate_count: Optional[int] = None
    bm25_candidate_count: Optional[int] = None
    faiss_candidate_count: Optional[int] = None
    rerank: Optional[Dict[str, Any]] = None
    context_expansion: Optional[Dict[str, Any]] = None
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
    chunk_index: Optional[int] = None
    score: Optional[float] = None
    faiss_score: Optional[float] = None
    bm25_score: Optional[float] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None
    faiss_rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    rrf_rank: Optional[int] = None
    original_rank: Optional[int] = None


class PromptBuildResult(BaseModel):
    system_instruction: str
    user_prompt: str
    context_text: str
    context_count: int
    mode: str
