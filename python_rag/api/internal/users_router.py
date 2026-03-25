from fastapi import APIRouter, HTTPException, Query

from python_rag.domain.constants.error_code import PARAM_ERROR, SUCCESS
from python_rag.domain.exceptions import AppException
from python_rag.schemas.common_schema import ApiResponse, createUserRequest, UserItem, UserListResponse
from python_rag.services.user_service import create_user, get_latest_users 


router = APIRouter(prefix="/internal", tags=["users"])

@router.post("/create", response_model=ApiResponse)
def create_user_api(req: createUserRequest):
    try:
        row = create_user(req.name)
        return ApiResponse(
            code=SUCCESS,
            message="ok",
            data=UserItem(**row),
        )
    except AppException as e:
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
            code=SUCCESS,
            message="ok",
            data=data,
        )
    except AppException as e:
        raise HTTPException(status_code=500, detail={"code": e.code, "message": e.message})
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": PARAM_ERROR, "message": "invalid limit"})