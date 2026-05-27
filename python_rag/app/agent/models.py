import json
from typing import Any, Dict, Optional

from python_rag.infra.mysql import get_mysql_connection


_UNSET = object()


def _json_dumps(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _normalize_agent_run(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None

    for field in ("input_json", "output_json", "meta_json"):
        row[field] = _json_loads(row.get(field))
    return row


def _normalize_agent_step(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None

    for field in ("input_json", "output_json"):
        row[field] = _json_loads(row.get(field))
    return row


def _normalize_agent_tool_call(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None

    for field in ("arguments_json", "result_json"):
        row[field] = _json_loads(row.get(field))
    return row


def _add_json_update(fields, params, column: str, value: Any) -> None:
    if value is not _UNSET:
        fields.append("{0}=%s".format(column))
        params.append(_json_dumps(value))


def _add_text_update(fields, params, column: str, value: Any) -> None:
    if value is not _UNSET:
        fields.append("{0}=%s".format(column))
        params.append(value)


def _add_optional_update(fields, params, column: str, value: Any) -> None:
    if value is not None:
        fields.append("{0}=%s".format(column))
        params.append(value)


def create_agent_run(
    agent_name: str,
    trace_id: Optional[str] = None,
    agent_version: Optional[str] = None,
    model: Optional[str] = None,
    status: str = "RUNNING",
    session_id: Optional[int] = None,
    user_message_id: Optional[int] = None,
    input_data: Optional[Any] = None,
    output_data: Optional[Any] = None,
    meta: Optional[Any] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    error_message: Optional[str] = None,
) -> int:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO agent_runs (
                    trace_id,
                    agent_name,
                    agent_version,
                    model,
                    status,
                    session_id,
                    user_message_id,
                    input_json,
                    output_json,
                    meta_json,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cost_usd,
                    error_message
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    trace_id,
                    agent_name,
                    agent_version,
                    model,
                    status,
                    session_id,
                    user_message_id,
                    _json_dumps(input_data),
                    _json_dumps(output_data),
                    _json_dumps(meta),
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cost_usd,
                    error_message,
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_agent_run(run_id: int) -> Optional[Dict[str, Any]]:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    trace_id,
                    agent_name,
                    agent_version,
                    model,
                    status,
                    session_id,
                    user_message_id,
                    input_json,
                    output_json,
                    meta_json,
                    total_steps,
                    total_tool_calls,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cost_usd,
                    error_message,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                FROM agent_runs
                WHERE id=%s
                """,
                (run_id,),
            )
            return _normalize_agent_run(cursor.fetchone())
    finally:
        conn.close()


def update_agent_run(
    run_id: int,
    status: Optional[str] = None,
    output_data: Any = _UNSET,
    meta: Any = _UNSET,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    error_message: Any = _UNSET,
    finished: bool = False,
) -> None:
    fields = []
    params = []

    _add_optional_update(fields, params, "status", status)
    _add_json_update(fields, params, "output_json", output_data)
    _add_json_update(fields, params, "meta_json", meta)
    _add_optional_update(fields, params, "prompt_tokens", prompt_tokens)
    _add_optional_update(fields, params, "completion_tokens", completion_tokens)
    _add_optional_update(fields, params, "total_tokens", total_tokens)
    _add_optional_update(fields, params, "cost_usd", cost_usd)
    _add_text_update(fields, params, "error_message", error_message)
    if finished:
        fields.append("finished_at=CURRENT_TIMESTAMP")

    if not fields:
        return

    params.append(run_id)
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE agent_runs SET {0} WHERE id=%s".format(", ".join(fields)),
                tuple(params),
            )
    finally:
        conn.close()


def get_next_agent_step_index(run_id: int) -> int:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(MAX(step_index) + 1, 0) AS next_step_index
                FROM agent_steps
                WHERE run_id=%s
                """,
                (run_id,),
            )
            row = cursor.fetchone() or {}
            return int(row.get("next_step_index") or 0)
    finally:
        conn.close()


def list_agent_steps(run_id: int) -> list:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    run_id,
                    step_index,
                    step_type,
                    name,
                    status,
                    model,
                    input_json,
                    reasoning_summary,
                    decision,
                    output_json,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    latency_ms,
                    error_message,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                FROM agent_steps
                WHERE run_id=%s
                ORDER BY step_index ASC, id ASC
                """,
                (run_id,),
            )
            return [
                _normalize_agent_step(row)
                for row in cursor.fetchall()
            ]
    finally:
        conn.close()


def create_agent_step(
    run_id: int,
    step_index: int,
    step_type: str = "decision",
    name: Optional[str] = None,
    status: str = "RUNNING",
    model: Optional[str] = None,
    input_data: Optional[Any] = None,
    reasoning_summary: Optional[str] = None,
    decision: Optional[str] = None,
    output_data: Optional[Any] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    latency_ms: Optional[int] = None,
    error_message: Optional[str] = None,
) -> int:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO agent_steps (
                    run_id,
                    step_index,
                    step_type,
                    name,
                    status,
                    model,
                    input_json,
                    reasoning_summary,
                    decision,
                    output_json,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    latency_ms,
                    error_message
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    run_id,
                    step_index,
                    step_type,
                    name,
                    status,
                    model,
                    _json_dumps(input_data),
                    reasoning_summary,
                    decision,
                    _json_dumps(output_data),
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    latency_ms,
                    error_message,
                ),
            )
            step_id = cursor.lastrowid
            cursor.execute(
                """
                UPDATE agent_runs
                SET total_steps=total_steps + 1
                WHERE id=%s
                """,
                (run_id,),
            )
            return step_id
    finally:
        conn.close()


def update_agent_step(
    step_id: int,
    status: Optional[str] = None,
    reasoning_summary: Any = _UNSET,
    decision: Any = _UNSET,
    output_data: Any = _UNSET,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    latency_ms: Optional[int] = None,
    error_message: Any = _UNSET,
    finished: bool = False,
) -> None:
    fields = []
    params = []

    _add_optional_update(fields, params, "status", status)
    _add_text_update(fields, params, "reasoning_summary", reasoning_summary)
    _add_text_update(fields, params, "decision", decision)
    _add_json_update(fields, params, "output_json", output_data)
    _add_optional_update(fields, params, "prompt_tokens", prompt_tokens)
    _add_optional_update(fields, params, "completion_tokens", completion_tokens)
    _add_optional_update(fields, params, "total_tokens", total_tokens)
    _add_optional_update(fields, params, "latency_ms", latency_ms)
    _add_text_update(fields, params, "error_message", error_message)
    if finished:
        fields.append("finished_at=CURRENT_TIMESTAMP")

    if not fields:
        return

    params.append(step_id)
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE agent_steps SET {0} WHERE id=%s".format(", ".join(fields)),
                tuple(params),
            )
    finally:
        conn.close()


def create_agent_tool_call(
    run_id: int,
    step_id: int,
    tool_name: str,
    tool_call_id: Optional[str] = None,
    status: str = "RUNNING",
    arguments: Optional[Any] = None,
    result: Optional[Any] = None,
    result_preview: Optional[str] = None,
    latency_ms: Optional[int] = None,
    error_message: Optional[str] = None,
) -> int:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO agent_tool_calls (
                    run_id,
                    step_id,
                    tool_call_id,
                    tool_name,
                    status,
                    arguments_json,
                    result_json,
                    result_preview,
                    latency_ms,
                    error_message
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    run_id,
                    step_id,
                    tool_call_id,
                    tool_name,
                    status,
                    _json_dumps(arguments),
                    _json_dumps(result),
                    result_preview,
                    latency_ms,
                    error_message,
                ),
            )
            tool_call_row_id = cursor.lastrowid
            cursor.execute(
                """
                UPDATE agent_runs
                SET total_tool_calls=total_tool_calls + 1
                WHERE id=%s
                """,
                (run_id,),
            )
            return tool_call_row_id
    finally:
        conn.close()


def update_agent_tool_call(
    tool_call_row_id: int,
    status: Optional[str] = None,
    result: Any = _UNSET,
    result_preview: Any = _UNSET,
    latency_ms: Optional[int] = None,
    error_message: Any = _UNSET,
    finished: bool = False,
) -> None:
    fields = []
    params = []

    _add_optional_update(fields, params, "status", status)
    _add_json_update(fields, params, "result_json", result)
    _add_text_update(fields, params, "result_preview", result_preview)
    _add_optional_update(fields, params, "latency_ms", latency_ms)
    _add_text_update(fields, params, "error_message", error_message)
    if finished:
        fields.append("finished_at=CURRENT_TIMESTAMP")

    if not fields:
        return

    params.append(tool_call_row_id)
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE agent_tool_calls SET {0} WHERE id=%s".format(", ".join(fields)),
                tuple(params),
            )
    finally:
        conn.close()


def list_agent_tool_calls(run_id: int) -> list:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    run_id,
                    step_id,
                    tool_call_id,
                    tool_name,
                    status,
                    arguments_json,
                    result_json,
                    result_preview,
                    latency_ms,
                    error_message,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                FROM agent_tool_calls
                WHERE run_id=%s
                ORDER BY id ASC
                """,
                (run_id,),
            )
            return [
                _normalize_agent_tool_call(row)
                for row in cursor.fetchall()
            ]
    finally:
        conn.close()
