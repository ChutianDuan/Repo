from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[Any] = None


class DependencyHealth(BaseModel):
    ok: bool
    code: Optional[int] = None
    message: Optional[str] = None


class HealthData(BaseModel):
    ok: bool
    mysql: DependencyHealth
    redis: DependencyHealth


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class UserItem(BaseModel):
    id: int
    name: str
    created_at: str


class UserListData(BaseModel):
    count: int
    items: List[UserItem]
