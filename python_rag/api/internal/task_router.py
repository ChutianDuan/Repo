from fastapi import APIRouter, HTTPException, Query

from python_rag.schemas.task_schema import (
    SubmitPingTaskRequest,
    SubmitIngestTaskRequest,
)
from python_rag.services.task_service import (
    submit_ping_job,
    submit_ingest_job,
    get_task_status,
    list_tasks,
    list_tasks_by_entity,
)

router = APIRouter(prefix="/internal", tags=["tasks"])


@router.post("/jobs/ping")
def create_ping_job(req: SubmitPingTaskRequest):
    seconds = int(req.seconds)
    if seconds <= 0 or seconds > 60:
        raise HTTPException(status_code=400, detail="seconds must be between 1 and 60")
    return submit_ping_job(seconds)


@router.post("/jobs/ingest")
def create_ingest_job(req: SubmitIngestTaskRequest):
    doc_id = int(req.doc_id)
    if doc_id <= 0:
        raise HTTPException(status_code=400, detail="doc_id must be positive")
    return submit_ingest_job(doc_id)


@router.get("/tasks/{task_id}")
def query_task_status(task_id):
    return get_task_status(task_id)


@router.get("")
def query_task_list(
    limit: int = Query(20, ge=1, le=100),
    state: str = Query(None),
):
    return list_tasks(limit=limit, state=state)


@router.get("/entity/{entity_type}/{entity_id}")
def query_tasks_by_entity(
    entity_type: str,
    entity_id: int,
    limit: int = Query(20, ge=1, le=100),
):
    if entity_id <= 0:
        raise HTTPException(status_code=400, detail="entity_id must be positive")
    return list_tasks_by_entity(entity_type=entity_type, entity_id=entity_id, limit=limit)