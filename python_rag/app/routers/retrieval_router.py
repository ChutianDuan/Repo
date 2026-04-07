from fastapi import APIRouter, HTTPException

from python_rag.core.errors import AppError
from python_rag.modules.retrieval.service import search_in_document
from python_rag.modules.retrieval.schemas import SearchRequest, SearchResponse

router = APIRouter(prefix="/internal", tags=["retrieval"])

@router.post("/search", response_model=SearchResponse)
def internal_search(req: SearchRequest):
    try:
        result = search_in_document(
            doc_id=req.doc_id,
            query=req.query,
            top_k=req.top_k,
        )
        return {
            "code": 0,
            "message": "ok",
            "data": result,
        }
    except AppError as e:
        raise HTTPException(status_code=400, detail=e.message)