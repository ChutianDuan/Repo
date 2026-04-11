from fastapi import APIRouter, HTTPException

from python_rag.core.errors import AppError
from python_rag.modules.chat.schemas import SubmitChatJobRequest
from python_rag.modules.chat.service import submit_chat_job

router = APIRouter(prefix="/internal/jobs", tags=["chat"])

@router.post("/chat")
def submit_chat_job_endpoint(request: SubmitChatJobRequest):
    try:
        return submit_chat_job(
            session_id=request.session_id,
            doc_id=request.doc_id,
            user_message_id=request.user_message_id,
            top_k=request.top_k,
        )
    except AppError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "internal_error", "message": str(e)})
