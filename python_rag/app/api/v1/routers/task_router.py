from fastapi import APIRouter, Query

from python_rag.app.core.error_codes import ERR_INVALID_REQUEST
from python_rag.app.core.errors import AppError
from python_rag.app.modules.tasks.schemas import (
    SubmitPingTaskRequest,
    SubmitIngestTaskRequest,
)
from python_rag.app.modules.tasks.service import (
    submit_ping_job,
    submit_ingest_job,
    get_task_status,
    list_tasks,
    list_tasks_by_entity,
)
from python_rag.app.shared.common import api_response
from python_rag.app.shared.schemas import ApiResponse

router = APIRouter(prefix="/internal", tags=["tasks"])


@router.post("/jobs/ping", response_model=ApiResponse)
def create_ping_job(req: SubmitPingTaskRequest):
    seconds = int(req.seconds)
    if seconds <= 0 or seconds > 60:
        raise AppError(ERR_INVALID_REQUEST, "seconds must be between 1 and 60")
    return api_response(submit_ping_job(seconds))


@router.post("/jobs/ingest", response_model=ApiResponse)
def create_ingest_job(req: SubmitIngestTaskRequest):
    doc_id = int(req.doc_id)
    if doc_id <= 0:
        raise AppError(ERR_INVALID_REQUEST, "doc_id must be positive")
    return api_response(submit_ingest_job(doc_id))


@router.get("/tasks/{task_id}", response_model=ApiResponse)
def query_task_status(task_id):
    return api_response(get_task_status(task_id))


@router.get("/tasks", response_model=ApiResponse)
def query_task_list(
    limit: int = Query(20, ge=1, le=100),
    state: str = Query(None),
):
    return api_response(list_tasks(limit=limit, state=state))


@router.get("/entity/{entity_type}/{entity_id}", response_model=ApiResponse)
def query_tasks_by_entity(
    entity_type: str,
    entity_id: int,
    limit: int = Query(20, ge=1, le=100),
):
    if entity_id <= 0:
        raise AppError(ERR_INVALID_REQUEST, "entity_id must be positive")
    return api_response(
        list_tasks_by_entity(entity_type=entity_type, entity_id=entity_id, limit=limit)
    )
