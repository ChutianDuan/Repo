from fastapi import FastAPI

from python_rag.core.errors import AppError
from python_rag.core.exception_handlers import (
    app_error_handler,
    generic_exception_handler,
)

from python_rag.app.routers.health_router import router as health_router
from python_rag.app.routers.task_router import router as task_router
from python_rag.app.routers.document_router import router as document_router
from python_rag.app.routers.users_router import router as users_router
from python_rag.app.routers.retrieval_router import router as retrieval_router
from python_rag.app.routers.session_router import router as session_router
from python_rag.app.routers.chat_router import router as chat_router
from python_rag.app.routers.chat_stream_router import router as chat_stream_router

app = FastAPI(
    title="Python RAG",
    version="0.1.0",
    description="Internal Python service for ingest, retrieval and chat tasks.",
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(health_router)
app.include_router(task_router)
app.include_router(chat_router)
app.include_router(document_router)
app.include_router(users_router)
app.include_router(retrieval_router)
app.include_router(session_router)
app.include_router(chat_stream_router)
