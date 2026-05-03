from fastapi import APIRouter

from python_rag.modules.chat.schemas import SubmitChatJobRequest
from python_rag.modules.chat.service import submit_chat_job

router = APIRouter(prefix="/internal/jobs", tags=["chat"])


@router.post("/chat")
def submit_chat_job_endpoint(request: SubmitChatJobRequest):
    return submit_chat_job(
        session_id=request.session_id,
        doc_id=request.doc_id,
        user_message_id=request.user_message_id,
        top_k=request.top_k,
    )
