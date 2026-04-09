from python_rag.modules.ingest.service import run_ingest_for_document
from python_rag.modules.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="python_rag.tasks.ingest_document")
def ingest_task(self, doc_id: int):
    celery_task_id = self.request.id

    def progress_callback(state: str, meta: dict):
        self.update_state(state=state, meta=meta)

    return run_ingest_for_document(
        doc_id=doc_id,
        celery_task_id=celery_task_id,
        progress_callback=progress_callback,
    )