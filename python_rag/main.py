import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import APP_NAME, APP_VERSION
from .constants import INTERNAL_ERROR
from .exceptions import AppException
from .logger import logger
from .routers.health import router as health_router
from .routers.users import router as users_router

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Minimal backend prototype for MySQL + Redis + Python service",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Day 5 开发阶段先放开，后面再收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration = (time.time() - start) * 1000
        status_code = response.status_code if response else 500
        logger.info(
            "%s %s -> %s (%.2f ms)",
            request.method,
            request.url.path,
            status_code,
            duration,
        )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.exception("AppException occurred")
    return JSONResponse(
        status_code=500,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception occurred")
    return JSONResponse(
        status_code=500,
        content={
            "code": INTERNAL_ERROR,
            "message": "internal server error",
            "data": str(exc),
        },
    )


@app.get("/")
def root():
    return {
        "code": 0,
        "message": "service is running",
        "data": {
            "docs": "/docs",
            "redoc": "/redoc",
            "version": APP_VERSION,
        },
    }


app.include_router(health_router)
app.include_router(users_router)