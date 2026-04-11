from typing import Any, Dict, List


def format_message(
    message: Dict[str, Any],
    citations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "message_id": message["message_id"],
        "session_id": message["session_id"],
        "role": message["role"],
        "content": message.get("content") or "",
        "status": message.get("status") or "UNKNOWN",
        "citations": citations or [],
        "meta": message.get("meta") or {},
        "created_at": message.get("created_at"),
        "updated_at": message.get("updated_at"),
    }


def format_message_list(
    messages: List[Dict[str, Any]],
    citations_map: Dict[int, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    result = []
    for msg in messages:
        message_id = msg["message_id"]
        result.append(
            format_message(
                message=msg,
                citations=citations_map.get(message_id, []),
            )
        )
    return result
