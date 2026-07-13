from typing import Any, Dict, Optional

from python_rag.app.core.error_codes import ERR_STREAM_ABORTED
from python_rag.app.shared.sse import build_sse_event


def build_delta_event(delta: str, index: int) -> str:
    return build_sse_event({
        "type": "delta",
        "delta": delta,
        "index": index,
    })

def build_done_event(meta: Optional[Dict[str, Any]] = None) -> str:
    payload = {
        "type": "done",
        "message": "stream finished",
    }
    if meta is not None:
        payload["meta"] = meta
    return build_sse_event(payload)

def build_error_event(
    message: str,
    code: int = ERR_STREAM_ABORTED,
    data: Any = None,
) -> str:
    return build_sse_event({
        "type": "error",
        "code": code,
        "message": message,
        "data": data,
    })


__all__ = [
    "build_delta_event",
    "build_done_event",
    "build_error_event",
    "build_sse_event",
]
