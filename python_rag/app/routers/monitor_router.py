from fastapi import APIRouter

from python_rag.modules.monitor.service import get_monitor_overview


router = APIRouter(prefix="/internal/monitor", tags=["monitor"])


@router.get("/overview")
def monitor_overview():
    return get_monitor_overview()
