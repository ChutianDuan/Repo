import json
from python_rag.infra.mysql import get_mysql_connection
from python_rag.infra.schema_support import has_column


def _task_select_fields() -> str:
    fields = [
        "id",
        "celery_task_id",
        "type",
        "entity_type",
        "entity_id",
        "state",
        "progress",
        "meta_json",
        "error",
        "created_at",
    ]
    if has_column("tasks", "updated_at"):
        fields.append("updated_at")
    return ", ".join(fields)


def create_task_record(celery_task_id, task_type, entity_type, entity_id,
                       state, progress=0, meta=None, error=None):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tasks (
                    celery_task_id, type, entity_type, entity_id,
                    state, progress, meta_json, error
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    celery_task_id,
                    task_type,
                    entity_type,
                    entity_id,
                    state,
                    progress,
                    json.dumps(meta or {}, ensure_ascii=False),
                    error,
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def update_task_record(celery_task_id, state=None, progress=None, meta=None, error=None):
    conn = get_mysql_connection()
    try:
        fields = []
        params = []

        if state is not None:
            fields.append("state=%s")
            params.append(state)

        if progress is not None:
            fields.append("progress=%s")
            params.append(progress)

        if meta is not None:
            fields.append("meta_json=%s")
            params.append(json.dumps(meta, ensure_ascii=False))

        if error is not None:
            fields.append("error=%s")
            params.append(error)

        if not fields:
            return

        params.append(celery_task_id)

        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE tasks SET {0} WHERE celery_task_id=%s".format(", ".join(fields)),
                params,
            )
    finally:
        conn.close()


def get_task_by_celery_id(celery_task_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT {fields}
                FROM tasks
                WHERE celery_task_id=%s
                """.format(fields=_task_select_fields()),
                (celery_task_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            if row.get("meta_json"):
                try:
                    row["meta_json"] = json.loads(row["meta_json"])
                except Exception:
                    pass

            return row
    finally:
        conn.close()


def list_task_records(limit=20, state=None):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            if state:
                cursor.execute(
                    """
                    SELECT {fields}
                    FROM tasks
                    WHERE state=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """.format(fields=_task_select_fields()),
                    (state, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT {fields}
                    FROM tasks
                    ORDER BY id DESC
                    LIMIT %s
                    """.format(fields=_task_select_fields()),
                    (limit,),
                )

            rows = cursor.fetchall()
            for row in rows:
                if row.get("meta_json"):
                    try:
                        row["meta_json"] = json.loads(row["meta_json"])
                    except Exception:
                        pass
            return rows
    finally:
        conn.close()


def list_task_records_by_entity(entity_type, entity_id, limit=20):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT {fields}
                FROM tasks
                WHERE entity_type=%s AND entity_id=%s
                ORDER BY id DESC
                LIMIT %s
                """.format(fields=_task_select_fields()),
                (entity_type, entity_id, limit),
            )

            rows = cursor.fetchall()
            for row in rows:
                if row.get("meta_json"):
                    try:
                        row["meta_json"] = json.loads(row["meta_json"])
                    except Exception:
                        pass
            return rows
    finally:
        conn.close()
