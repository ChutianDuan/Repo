# python_rag/routers/chat_stream_router.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from python_rag.modules.chat.schemas import ChatStreamRequest
from python_rag.modules.chat.streaming_service import stream_chat_for_message

router = APIRouter(prefix="/internal/chat", tags=["chat-stream"])


@router.post("/stream")
def chat_stream(req: ChatStreamRequest):
    generator = stream_chat_for_message(
        session_id=req.session_id,
        doc_id=req.doc_id,
        user_message_id=req.user_message_id,
        top_k=req.top_k,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )