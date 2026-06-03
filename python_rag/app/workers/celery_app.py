from celery import Celery
from python_rag.app.core.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "python_rag",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "python_rag.app.workers.worker_tasks.ping_task",
        "python_rag.app.workers.worker_tasks.ingest_task",
        "python_rag.app.workers.worker_tasks.chat_task",
        "python_rag.app.agent.memory.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Taipei",
    enable_utc=False,
    task_track_started=True,
    result_expires=3600 * 24,
)