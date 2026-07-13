import json
from typing import Any, Dict, Optional


def parse_last_event_id(last_event_id: Optional[str]) -> int:
    if last_event_id is None:
        return 0
    try:
        return max(0, int(str(last_event_id).strip()))
    except (TypeError, ValueError):
        return 0


def resume_requested(last_event_id: Optional[str]) -> bool:
    return last_event_id is not None and str(last_event_id).strip() != ""


def build_sse_event(
    data: Dict[str, Any],
    event: Optional[str] = None,
    event_id: Optional[int] = None,
) -> str:
    payload = dict(data)
    lines = []
    if event_id is not None:
        lines.append("id: {0}".format(event_id))
        payload["event_id"] = event_id
    if event:
        lines.append("event: {0}".format(event))
    lines.append("data: {0}".format(json.dumps(payload, ensure_ascii=False)))
    return "\n".join(lines) + "\n\n"


def build_sse_comment(comment: str = "keep-alive") -> str:
    return ": {0}\n\n".format(comment.replace("\n", " "))


def add_sse_event_id(raw_event: str, event_id: int) -> str:
    """Add an SSE id and mirror it in a JSON data payload."""
    event_name = None
    data_lines = []
    for line in raw_event.replace("\r\n", "\n").splitlines():
        if line.startswith("event:"):
            event_name = line[6:].strip() or None
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if not data_lines:
        return "id: {0}\n{1}".format(event_id, raw_event.lstrip("\n"))

    try:
        payload = json.loads("\n".join(data_lines))
    except (TypeError, ValueError):
        return "id: {0}\n{1}".format(event_id, raw_event.lstrip("\n"))

    if not isinstance(payload, dict):
        return "id: {0}\n{1}".format(event_id, raw_event.lstrip("\n"))
    return build_sse_event(payload, event=event_name, event_id=event_id)


def is_terminal_sse(raw_event: str) -> bool:
    for line in raw_event.replace("\r\n", "\n").splitlines():
        if not line.startswith("data:"):
            continue
        try:
            payload = json.loads(line[5:].lstrip())
        except (TypeError, ValueError):
            return False
        return isinstance(payload, dict) and payload.get("type") in {"done", "error"}
    return False


__all__ = [
    "add_sse_event_id",
    "build_sse_comment",
    "build_sse_event",
    "is_terminal_sse",
    "parse_last_event_id",
    "resume_requested",
]
