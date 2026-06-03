from fastapi import APIRouter

from python_rag.app.modules.retrieval.service import search_in_documents
from python_rag.app.modules.retrieval.schemas import SearchRequest, SearchResponse
from python_rag.app.shared.common import api_response

router = APIRouter(prefix="/internal", tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)
def internal_search(req: SearchRequest):
    result = search_in_documents(
        doc_id=req.doc_id,
        doc_ids=req.doc_ids,
        user_id=req.user_id,
        query=req.query,
        top_k=req.top_k,
        relevant_chunk_ids=req.relevant_chunk_ids,
        relevant_chunk_indexes=req.relevant_chunk_indexes,
    )
    return api_response(result)
