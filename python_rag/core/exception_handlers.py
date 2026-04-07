# FastaAPI 异常服务
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from python_rag.core.error_codes import ERR_INTERNAL_ERROR
from python_rag.core.errors import AppError

logger = logging.getLogger(__name__)


def build_error_response(code: int, message: str, data=None):
    return {"code": code, "message": message, "data": data}


async def app_error_handler(request: Request, exc: AppError):
    logger.warning(
        "app error path=%s code=%s message=%s",
        request.url.path,
        exc.code,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=build_error_response(exc.code, exc.message, exc.data),
    )


async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=build_error_response(ERR_INTERNAL_ERROR, "internal server error"),
    )