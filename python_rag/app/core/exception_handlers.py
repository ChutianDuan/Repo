# FastAPI exception handlers

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from python_rag.app.core.error_codes import ERR_INTERNAL_ERROR, ERR_INVALID_REQUEST
from python_rag.app.core.errors import AppError
from python_rag.app.core.logger import logger
from python_rag.app.shared.common import api_response


def build_error_response(code: int, message: str, data=None):
    return api_response(code=code, message=message, data=data)


def _json_error(status_code: int, code: int, message: str, data=None):
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(build_error_response(code, message, data)),
    )


async def app_error_handler(request: Request, exc: AppError):
    logger.warning(
        "app error path=%s code=%s message=%s",
        request.url.path,
        exc.code,
        exc.message,
    )
    return _json_error(exc.http_status, exc.code, exc.message, exc.data)


async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
):
    logger.warning("request validation failed path=%s", request.url.path)
    return _json_error(
        422,
        ERR_INVALID_REQUEST,
        "request validation failed",
        {"errors": exc.errors()},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message = detail if isinstance(detail, str) else "request failed"
    data = None if isinstance(detail, str) else detail
    code = ERR_INVALID_REQUEST if exc.status_code < 500 else ERR_INTERNAL_ERROR
    logger.warning("http error path=%s status=%s", request.url.path, exc.status_code)
    return _json_error(exc.status_code, code, message, data)


async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled error path=%s", request.url.path)
    return _json_error(500, ERR_INTERNAL_ERROR, "internal server error")
