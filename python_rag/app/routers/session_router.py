from fastapi import APIRouter, HTTPException, Query

from python_rag.core.errors import AppError
from python_rag.modules.sessions.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    CreateMessageRequest,
    CreateMessageResponse,
    ListMessagesResponse,
    UpdateMessageStatusRequest,
    UpdateMessageStatusResponse,
)
from python_rag.modules.sessions.service import (
    create_session_service,
    create_message_service,
    list_messages_service,
    update_session_message_status_service,
)

router = APIRouter(prefix="/internal/sessions", tags=["sessions"])


@router.post("", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest):
    try:
        data = create_session_service(
            user_id=req.user_id,
            title=req.title,
        )
        return {"code": 0, "message": "ok", "data": data}
    except AppError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/messages", response_model=CreateMessageResponse)
def create_session_message(session_id: int, req: CreateMessageRequest):
    try:
        data = create_message_service(
            session_id=session_id,
            role=req.role,
            content=req.content,
            status=req.status,
        )
        return {"code": 0, "message": "ok", "data": data}
    except AppError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{session_id}/messages", response_model=ListMessagesResponse)
def list_session_messages(session_id: int, limit: int = Query(100, ge=1, le=500)):
    try:
        data = list_messages_service(session_id=session_id, limit=limit)
        return {"code": 0, "message": "ok", "data": data}
    except AppError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.post("/{session_id}/messages/{message_id}/status", response_model=UpdateMessageStatusResponse)
def update_session_message_status(
    session_id: int,
    message_id: int,
    req: UpdateMessageStatusRequest,
):
    try:
        data = update_session_message_status_service(
            session_id=session_id,
            message_id=message_id,
            status=req.status,
        )
        return {"code": 0, "message": "ok", "data": data}
    except AppError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
