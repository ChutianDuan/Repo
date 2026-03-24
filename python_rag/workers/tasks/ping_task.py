import time

from python_rag.domain.constants.task_state import TaskState
from python_rag.repos.task_repo import update_task_record
from python_rag.workers.celery_app import celery_app


@celery_app.task(bind=True, name="python_rag.tasks.ping")
def ping_task(self, seconds=5):
    celery_task_id = self.request.id

    update_task_record(
        celery_task_id=celery_task_id,
        state=TaskState.STARTED,
        progress=0,
        meta={"stage": "started"},
    )

    for i in range(seconds):
        progress = int((i + 1) * 100 / seconds)

        self.update_state(
            state=TaskState.PROGRESS,
            meta={
                "progress": progress,
                "current": i + 1,
                "total": seconds,
            },
        )

        update_task_record(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=progress,
            meta={
                "progress": progress,
                "current": i + 1,
                "total": seconds,
            },
        )

        time.sleep(1)

    result = {"message": "pong", "seconds": seconds}

    update_task_record(
        celery_task_id=celery_task_id,
        state=TaskState.SUCCESS,
        progress=100,
        meta=result,
    )

    return result