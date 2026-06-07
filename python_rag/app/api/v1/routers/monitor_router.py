from fastapi import APIRouter

from python_rag.app.modules.monitor.service import get_monitor_overview
from python_rag.app.shared.common import api_response
from python_rag.app.shared.schemas import ApiResponse


router = APIRouter(prefix="/internal/monitor", tags=["monitor"])


@router.get("/overview", response_model=ApiResponse)
def monitor_overview():
    return api_response(get_monitor_overview())
