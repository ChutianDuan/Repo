from typing import Any, Optional

from pydantic import BaseModel

from python_rag.app.core.error_codes import ERR_INTERNAL_ERROR


class ErrorResponse(BaseModel):
    code: int = ERR_INTERNAL_ERROR
    message: str
    data: Optional[Any] = None
