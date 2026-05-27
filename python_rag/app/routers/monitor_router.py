from fastapi import APIRouter

from python_rag.modules.monitor.service import get_monitor_overview
from python_rag.utils.common import ApiResponse, api_response


router = APIRouter(prefix="/internal/monitor", tags=["monitor"])


@router.get("/overview", response_model=ApiResponse)
def monitor_overview():
    return api_response(get_monitor_overview())
