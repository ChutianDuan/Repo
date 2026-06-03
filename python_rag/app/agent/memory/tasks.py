from typing import Any, Dict, Optional

from python_rag.app.agent.memory.session import run_session_summary_update
from python_rag.app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="python_rag.tasks.session_summary_update")
def session_summary_task(
    self,
    session_id: int,
    current_user_message_id: Optional[int] = None,
    source_until_message_id: Optional[int] = None,
) -> Dict[str, Any]:
    return run_session_summary_update(
        session_id=session_id,
        current_user_message_id=current_user_message_id,
        source_until_message_id=source_until_message_id,
    )


__all__ = [
    "session_summary_task",
]
