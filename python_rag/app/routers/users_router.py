from fastapi import APIRouter, HTTPException, Query

from python_rag.core.error_codes import  OK,ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError

from python_rag.modules.user.service import create_user, get_latest_users 

from python_rag.utils.common import ApiResponse, createUserRequest, UserItem, UserListResponse

router = APIRouter(prefix="/internal", tags=["users"])

@router.post("/create", response_model=ApiResponse)
def create_user_api(req: createUserRequest):
    try:
        row = create_user(req.name)
        return ApiResponse(
            code=OK,
            message="ok",
            data=UserItem(**row),
        )
    except AppError as e:
        raise HTTPException(status_code=500, detail={"code": e.code, "message": e.message})


@router.get("/latest", response_model=ApiResponse)
def latest_users_api(limit: int = Query(5, ge=1, le=50)):
    try:
        rows = get_latest_users(limit)
        data = UserListResponse(
            count=len(rows),
            data=[UserItem(**row) for row in rows],
        )
        return ApiResponse(
            code=OK,
            message="ok",
            data=data,
        )
    except AppError as e:
        raise HTTPException(status_code=500, detail={"code": e.code, "message": e.message})
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": ERR_INTERNAL_ERROR, "message": "invalid limit"})