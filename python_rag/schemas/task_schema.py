from typing import Any, Dict, Optional
from pydantic import BaseModel


class SubmitPingTaskRequest(BaseModel):
    seconds = 5


class SubmitIngestTaskRequest(BaseModel):
    doc_id = 0


class SubmitTaskResponse(BaseModel):
    db_task_id: int
    task_id: str
    state: str
    status_url: str


class TaskStatusResponse(BaseModel):
    task_id: str
    state: str
    progress: int
    meta: Optional[Dict[str, Any]] = None
    error: Optional[str] = None