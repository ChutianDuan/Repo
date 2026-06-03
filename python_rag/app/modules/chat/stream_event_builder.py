# Python dict 转成 SSE 文本

import json
from typing import Any, Dict, Optional


def build_sse_event(data: Dict[str, Any], event: Optional[str] = None) -> str:
    lines = []
    if event:
        lines.append("event: %s" % event)
    lines.append("data: %s" % json.dumps(data, ensure_ascii=False))
    return "\n".join(lines) + "\n\n"

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

def build_error_event(message: str) -> str:
    return build_sse_event({
        "type": "error",
        "message": message,
    })
