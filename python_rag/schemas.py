from typing import Any,List,Optional
from pydantic import BaseModel, Field

class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[Any] = None

class HealthData(BaseModel):
    mysql: bool |str
    redis: bool |str

class createUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)

class UserItem(BaseModel):
    id: int
    name: str
    created_at: str

class UserListResponse(ApiResponse):
    conunt: int
    data: List[UserItem]