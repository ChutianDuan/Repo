from typing import List

from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class UserItem(BaseModel):
    id: int
    name: str
    created_at: str


class UserListData(BaseModel):
    count: int
    items: List[UserItem]
