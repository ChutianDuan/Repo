from fastapi import APIRouter
from ..constants import SUCCESS
from ..schemas import ApiResponse, HealthData
from ..services.health_service import get_health_status

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=ApiResponse)
def health_check():
    status = get_health_status()
    return ApiResponse(
        code=SUCCESS,
        message="ok",
        data=HealthData(**status),
    )