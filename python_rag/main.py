from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .logger import logger
from .routers.health import router as health_router
from .routers.users import router as users_router

app = FastAPI(
    title="AI Project Minimal API",
    description="A minimal API for AI project with MySQL and Redis integration",
    version="1.0.0",)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception occurred")
    return JSONResponse(
        status_code=500,
        content={
            "code" : 500,
            "message": "Internal Server Error",
            "details": str(exc)
        },
    )

@app.get("/")
def root():
    return {
        "code": 0,
        "message": "Welcome to the AI Project Minimal API",
        "data":{
            "docs": "/docs",
            "redoc": "/redoc",
        },
    }

app.include_router(health_router)
app.include_router(users_router)