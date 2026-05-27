from fastapi import FastAPI

from python_rag.core.errors import AppError
from python_rag.core.exception_handlers import (
    app_error_handler,
    generic_exception_handler,
)
from python_rag.app.routers import register_routers

app = FastAPI(
    title="Python RAG",
    version="0.1.0",
    description="Internal Python service for ingest, retrieval and chat tasks.",
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

register_routers(app)
