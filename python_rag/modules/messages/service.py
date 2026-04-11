from python_rag.modules.messages.repo import list_messages_by_session_id
from python_rag.modules.chat.repo import list_citations_by_message_ids
from python_rag.modules.messages.formatter import format_message_list


def get_session_messages(session_id: int, limit: int = 100):
    messages = list_messages_by_session_id(session_id=session_id, limit=limit)

    message_ids = [m["message_id"] for m in messages]
    citations_map = list_citations_by_message_ids(message_ids)

    formatted_messages = format_message_list(
        messages=messages,
        citations_map=citations_map,
    )

    return {
        "session_id": session_id,
        "messages": formatted_messages,
    }

def handle_list_session_messages(session_id: int, limit: int = 100):
    data = get_session_messages(session_id=session_id, limit=limit)
    return {
        "code": 0,
        "message": "ok",
        "data": data,
    }