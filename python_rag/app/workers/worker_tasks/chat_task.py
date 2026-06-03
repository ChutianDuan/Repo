from python_rag.app.workers.celery_app import celery_app
from python_rag.app.modules.chat.runtime_service  import run_chat_for_message


@celery_app.task(bind=True, name="python_rag.tasks.chat_generate")
def chat_task(self, session_id, doc_id=None, user_message_id=None, top_k=3, doc_ids=None):
    celery_task_id = self.request.id

    def progress_callback(state, meta):
        self.update_state(state=state, meta=meta)

    return run_chat_for_message(
        session_id=session_id,
        doc_id=doc_id,
        doc_ids=doc_ids or [],
        user_message_id=user_message_id,
        top_k=top_k,
        celery_task_id=celery_task_id,
        progress_callback=progress_callback,
    )
