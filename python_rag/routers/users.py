from fastapi import APIRouter, HTTPException, Query

from ..cache import get_redis_client
from ..logger import logger
from ..models import  create_user, get_latest_users
from ..schemas import ApiResponse, createUserRequest,UserItem, UserListResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/create", response_model=ApiResponse)
def create_user_api(request: createUserRequest):
    try:
        row = create_user(request.name)
        client = get_redis_client()
        client.set("user:last_created_name", request.name)
        return ApiResponse(data=UserItem(**row))
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")
@router.get("/latest", response_model=ApiResponse)
def latest_users_api(limit: int = Query(5, ge=1, le=100)):
    try:
        rows = get_latest_users(limit)
        return ApiResponse(data=UserListResponse(conunt=len(rows), data=[UserItem(**row) for row in rows]))
    except Exception as e:
        logger.error(f"Error fetching latest users: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch latest users")