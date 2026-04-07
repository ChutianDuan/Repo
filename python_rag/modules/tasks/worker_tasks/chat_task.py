from python_rag.modules.tasks.celery_app import celery_app
from python_rag.services.chat_runtime_service import run_chat_for_message


@celery_app.task(bind=True, name="python_rag.tasks.chat_generate")
def chat_task(self, session_id, doc_id, user_message_id, top_k=3):
    celery_task_id = self.request.id

    def progress_callback(state, meta):
        self.update_state(state=state, meta=meta)

    return run_chat_for_message(
        session_id=session_id,
        doc_id=doc_id,
        user_message_id=user_message_id,
        top_k=top_k,
        celery_task_id=celery_task_id,
        progress_callback=progress_callback,
    )