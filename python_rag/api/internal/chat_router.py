from fastapi import  APIRouter, HTTPException

from python_rag.domain.exceptions import AppException
from python_rag.schemas.chat_schema import SubmitChatJobRequest
from python_rag.services.chat_service import submit_chat_job

router = APIRouter(prefix="/internal/jobs", tags=["chat"])

@router.post("/chat")
def submit_chat_job_endpoint(request: SubmitChatJobRequest):
    try:
        task_id = submit_chat_job(
            session_id=request.session_id,
            doc_id=request.doc_id,
            user_message_id=request.user_message_id,
            top_k=request.top_k,
        )
        return {"task_id": task_id}
    except AppException as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "internal_error", "message": str(e)})
