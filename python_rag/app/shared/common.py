from typing import Any, Dict

from python_rag.app.core.error_codes import OK
from python_rag.app.shared.schemas import ApiResponse


def api_response(
    data: Any = None,
    message: str = "ok",
    code: int = OK,
) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
    }


__all__ = [
    "ApiResponse",
    "api_response",
]
