from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from python_rag.domain.exceptions import AppException
from python_rag.domain.logger import logger


from python_rag.api.internal.health_router import router as health_router
from python_rag.api.internal.task_router import router as task_router
from python_rag.api.internal.document_router import router as document_router
from python_rag.api.internal.users_router import router  as users_router
from python_rag.api.internal.retrieval_router import router as retrieval_router
from python_rag.api.internal.session_router import router as session_router
from python_rag.api.internal.chat_router import router as chat_router

app = FastAPI(title="Python RAG v2")

app.include_router(health_router)
app.include_router(task_router)
app.include_router(chat_router)
app.include_router(document_router)
app.include_router(users_router)
app.include_router(retrieval_router)
app.include_router(session_router)

@app.exception_handler(AppException)
async def handle_app_exception(request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "code": exc.code,
            "message": exc.message,
        },
    )


@app.exception_handler(Exception)
async def handle_unknown_exception(request, exc):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "code": 1999,
            "message": "internal server error",
        },
    )