from fastapi import APIRouter, HTTPException

from python_rag.domain.exceptions import ApiException

from python_rag.services.retrieval_service import search_in_document
from python_rag.schemas.retrieval_schema import SearchRequest, SearchResponse

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
    except ApiException as e:
        raise HTTPException(status_code=400, detail=e.message)