from typing import Any, Dict, Optional

from python_rag.app.agent.memory.updates import (
    run_session_summary_update,
    run_user_memory_update,
)
from python_rag.app.workers.celery_app import celery_app


# Celery 只负责调度，实际记忆选择、生成和落库逻辑都在 updates.py。
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


@celery_app.task(bind=True, name="python_rag.tasks.user_memory_update")
def user_memory_task(
    self,
    user_id: int,
    current_session_id: Optional[int] = None,
    current_user_message_id: Optional[int] = None,
    source_until_message_id: Optional[int] = None,
) -> Dict[str, Any]:
    return run_user_memory_update(
        user_id=user_id,
        current_session_id=current_session_id,
        current_user_message_id=current_user_message_id,
        source_until_message_id=source_until_message_id,
    )


__all__ = [
    "session_summary_task",
    "user_memory_task",
]
