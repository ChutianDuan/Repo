from importlib import import_module

from fastapi import FastAPI


ROUTER_MODULES = (
    "python_rag.app.api.v1.routers.health_router",
    "python_rag.app.api.v1.routers.agent_router",
    "python_rag.app.api.v1.routers.task_router",
    "python_rag.app.api.v1.routers.chat_router",
    "python_rag.app.api.v1.routers.document_router",
    "python_rag.app.api.v1.routers.users_router",
    "python_rag.app.api.v1.routers.retrieval_router",
    "python_rag.app.api.v1.routers.session_router",
    "python_rag.app.api.v1.routers.chat_stream_router",
    "python_rag.app.api.v1.routers.monitor_router",
)


def register_routers(app: FastAPI) -> None:
    for module_name in ROUTER_MODULES:
        module = import_module(module_name)
        app.include_router(module.router)
