from typing import Any,List,Optional
from pydantic import BaseModel, Field
from datetime import datetime

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
    created_at: datetime

class UserListResponse(ApiResponse):
    count: int
    data: List[UserItem]
class TaskCreateRequest(BaseModel):
    user_id: int
    task_type: str
    input_text: str

class TaskItem(BaseModel):
    id: int
    user_id: int
    task_type: str
    input_text: str
    status: str
    created_at: Any

class TaskListData(BaseModel):
    count: int
    data: List[TaskItem]

class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)

class RagQueryData(BaseModel):
    query: str
    answer: str
    sources: List[str]