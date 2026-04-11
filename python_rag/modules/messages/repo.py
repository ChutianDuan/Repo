import json

from python_rag.infra.mysql import get_mysql_connection
from python_rag.utils.to_iso import _to_iso


def _decode_meta(value):
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def _normalize_message_row(row):
    if not row:
        return None

    row["message_id"] = row.pop("id")
    row["created_at"] = _to_iso(row.get("created_at"))
    row["updated_at"] = _to_iso(row.get("updated_at"))
    row["meta"] = _decode_meta(row.pop("meta_json", None))
    return row


def create_message(session_id, role, content, status="SUCCESS", meta_json=None, meta=None):
    payload_meta = meta_json if meta_json is not None else meta

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages (session_id, role, content, status, meta_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    role,
                    content,
                    status,
                    json.dumps(payload_meta or {}, ensure_ascii=False),
                ),
            )
            message_id = cursor.lastrowid

            cursor.execute(
                """
                SELECT id, session_id, role, content, status, meta_json, created_at, updated_at
                FROM messages
                WHERE id=%s
                """,
                (message_id,),
            )
            return _normalize_message_row(cursor.fetchone())
    finally:
        conn.close()


def list_messages_by_session_id(session_id, limit=100):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    session_id,
                    role,
                    content,
                    status,
                    meta_json,
                    created_at,
                    updated_at
                FROM messages
                WHERE session_id=%s
                ORDER BY id ASC
                LIMIT %s
                """,
                (session_id, limit),
            )
            rows = cursor.fetchall()
            return [_normalize_message_row(row) for row in rows]
    finally:
        conn.close()


def list_recent_messages_by_session_id(session_id, limit=10):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    session_id,
                    role,
                    content,
                    status,
                    meta_json,
                    created_at,
                    updated_at
                FROM messages
                WHERE session_id=%s
                ORDER BY id DESC
                LIMIT %s
                """,
                (session_id, limit),
            )
            rows = cursor.fetchall()
            rows.reverse()
            return [_normalize_message_row(row) for row in rows]
    finally:
        conn.close()


def get_message_by_id(message_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, session_id, role, content, status, meta_json, created_at, updated_at
                FROM messages
                WHERE id=%s
                """,
                (message_id,),
            )
            return _normalize_message_row(cursor.fetchone())
    finally:
        conn.close()


def update_message_status(message_id, status):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE messages
                SET status=%s,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (status, message_id),
            )
    finally:
        conn.close()
