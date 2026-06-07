from fastapi import APIRouter, Query

from python_rag.app.modules.user.schemas import (
    CreateUserRequest,
    UserItem,
    UserListData,
)
from python_rag.app.modules.user.service import create_user, get_latest_users
from python_rag.app.shared.common import api_response
from python_rag.app.shared.schemas import ApiResponse

router = APIRouter(prefix="/internal/users", tags=["users"])


@router.post("", response_model=ApiResponse)
def create_user_api(req: CreateUserRequest):
    row = create_user(req.name)
    return api_response(UserItem(**row))


@router.get("/latest", response_model=ApiResponse)
def latest_users_api(limit: int = Query(5, ge=1, le=50)):
    rows = get_latest_users(limit)
    data = UserListData(
        count=len(rows),
        items=[UserItem(**row) for row in rows],
    )
    return api_response(data)
