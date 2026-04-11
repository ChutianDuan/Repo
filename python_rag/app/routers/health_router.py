from fastapi import APIRouter
from fastapi.responses import JSONResponse

from python_rag.core.error_codes import OK
from python_rag.modules.health.service import get_health_status
from python_rag.utils.common import ApiResponse, HealthData

router = APIRouter(prefix="/internal", tags=["health"])


@router.get("/health", response_model=ApiResponse)
def health():
    health_data = get_health_status()
    payload = ApiResponse(
        code=OK,
        message="ok",
        data=HealthData(**health_data),
    )
    return JSONResponse(
        status_code=200 if health_data["ok"] else 503,
        content=payload.model_dump(),
    )
