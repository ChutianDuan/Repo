from typing import Any, Optional

from pydantic import BaseModel

from python_rag.app.core.error_codes import OK


class ApiResponse(BaseModel):
    code: int = OK
    message: str = "ok"
    data: Optional[Any] = None


class IdResponse(BaseModel):
    id: int


class DeleteResponse(BaseModel):
    deleted: bool = True
