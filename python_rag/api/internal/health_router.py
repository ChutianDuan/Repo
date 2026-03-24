from fastapi import APIRouter

from python_rag.services.health_service import get_health_status
from python_rag.schemas.common_schema import ApiResponse, HealthData
from python_rag.domain.constants.error_code import  SUCCESS

router = APIRouter(prefix="/internal", tags=["health"])


@router.get("/health", response_model=ApiResponse)
def health():
    health_data = get_health_status()
    return ApiResponse(
        code=SUCCESS,
        message="ok",
        data=HealthData(**health_data),
    )