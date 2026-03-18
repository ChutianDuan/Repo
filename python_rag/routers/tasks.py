from fastapi import APIRouter, HTTPException, Query
from ..constants import PARAM_ERROR, SUCCESS
from ..exceptions import AppException
from ..schemas import ApiResponse, TaskCreateRequest, TaskItem, TaskListData
from ..services.tasks_service import create_task, get_latest_task_records


router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/create", response_model=ApiResponse)
def create_task_api(req: TaskCreateRequest):
    try:
        task_id = create_task(req.user_id, req.task_type, req.input_text)
        return ApiResponse(
            code=SUCCESS,
            message="ok",
            data=TaskItem(
                id=task_id,
                user_id=req.user_id,
                task_type=req.task_type,
                input_text=req.input_text,
            ),
        )
    except AppException as e:
        raise HTTPException(status_code=500, detail={"code": e.code, "message": e.message})
@router.get("/latest", response_model=ApiResponse)
def latest_tasks_api(limit: int = Query(5, ge=1, le=50)):
    try:
        rows = get_latest_task_records(limit)
        data = TaskListData(
            count=len(rows),
            data=[TaskItem(**row) for row in rows],
        )
        return ApiResponse(
            code=SUCCESS,
            message="ok",
            data=data,
        )
    except AppException as e:
        raise HTTPException(status_code=500, detail={"code": e.code, "message": e.message})
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": PARAM_ERROR, "message": "invalid limit"})