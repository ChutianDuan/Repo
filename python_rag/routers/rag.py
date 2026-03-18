from fastapi import APIRouter, HTTPException

from ..constants import SUCCESS
from ..exceptions import AppException
from ..schemas import ApiResponse, RagQueryRequest, RagQueryData
from ..services.rag_service import rag_query_service


router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=ApiResponse)
def rag_query_api(req: RagQueryRequest):
    try:
        row = rag_query_service(req.query)
        return ApiResponse(
            code=SUCCESS,
            message="ok",
            data=RagQueryData(**row),
        )
    except AppException as e:
        raise HTTPException(
            status_code=500,
            detail={"code": e.code, "message": e.message},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": 10000, "message": f"internal server error: {e}"},
        )