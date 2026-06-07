from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageRequest(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class PageResult(BaseModel, Generic[T]):
    total: int = Field(..., ge=0)
    items: List[T]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
