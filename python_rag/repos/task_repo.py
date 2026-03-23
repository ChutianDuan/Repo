# python_rag/repos/task_repo.py
import json
from python_rag.db import get_mysql_connection
from python_rag.constants.task_state import TaskState


def create_task(celery_task_id, task_type, entity_type, entity_id,
                state=TaskState.PENDING, progress=0, meta=None):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tasks (
                    celery_task_id, type, entity_type, entity_id,
                    state, progress, meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    celery_task_id,
                    task_type,
                    entity_type,
                    entity_id,
                    state,
                    progress,
                    json.dumps(meta or {}, ensure_ascii=False),
                )
            )
            return cursor.lastrowid
    finally:
        conn.close()


def update_task_state(celery_task_id, state, progress=None, meta=None, error=None):
    conn = get_mysql_connection()
    try:
        fields = ["state=%s"]
        params = [state]

        if progress is not None:
            fields.append("progress=%s")
            params.append(progress)

        if meta is not None:
            fields.append("meta_json=%s")
            params.append(json.dumps(meta, ensure_ascii=False))

        if error is not None:
            fields.append("error=%s")
            params.append(error)

        params.append(celery_task_id)

        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE tasks SET {0} WHERE celery_task_id=%s".format(", ".join(fields)),
                params
            )
    finally:
        conn.close()


def get_task_by_celery_id(celery_task_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, celery_task_id, type, entity_type, entity_id,
                       state, progress, meta_json, error, created_at, updated_at
                FROM tasks
                WHERE celery_task_id=%s
                """,
                (celery_task_id,)
            )
            return cursor.fetchone()
    finally:
        conn.close()