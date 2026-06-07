from fastapi import APIRouter

from python_rag.app.modules.chat.schemas import SubmitChatJobRequest
from python_rag.app.modules.chat.service import submit_chat_job
from python_rag.app.shared.common import api_response
from python_rag.app.shared.schemas import ApiResponse

router = APIRouter(prefix="/internal/jobs", tags=["chat"])


@router.post("/chat", response_model=ApiResponse)
def submit_chat_job_endpoint(request: SubmitChatJobRequest):
    return api_response(
        submit_chat_job(
            session_id=request.session_id,
            doc_id=request.doc_id,
            doc_ids=request.doc_ids,
            user_message_id=request.user_message_id,
            top_k=request.top_k,
        )
    )
