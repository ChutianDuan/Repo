from python_rag.app.infra.mysql import get_mysql_connection
from python_rag.app.infra.schema_support import has_column
from python_rag.app.shared.to_iso import _to_iso


def create_user(name: str):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO user_account (username) VALUES (%s)", (name,))
            user_id = cursor.lastrowid
            cursor.execute(
                "SELECT id, username AS name, created_at FROM user_account WHERE id = %s",
                (user_id,),
            )
            row = cursor.fetchone()
    finally:
        conn.close()
    row["created_at"] = _to_iso(row["created_at"])
    return row


def get_latest_users(limit: int = 5):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username AS name, created_at FROM user_account ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    for row in rows:
        row["created_at"] = _to_iso(row["created_at"])
    return rows


def supports_user_memory():
    return (
        has_column("user_account", "memory_summary")
        and has_column("user_account", "memory_message_id")
    )


def get_user_memory_by_id(user_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            fields = ["id"]
            if has_column("user_account", "memory_summary"):
                fields.append("memory_summary")
            if has_column("user_account", "memory_message_id"):
                fields.append("memory_message_id")
            if has_column("user_account", "memory_updated_at"):
                fields.append("memory_updated_at")
            cursor.execute(
                """
                SELECT {fields}
                FROM user_account
                WHERE id=%s
                """.format(fields=", ".join(fields)),
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            row.setdefault("memory_summary", "")
            row.setdefault("memory_message_id", None)
            if "memory_updated_at" in row:
                row["memory_updated_at"] = _to_iso(row.get("memory_updated_at"))
            return row
    finally:
        conn.close()


def update_user_memory(user_id, memory_summary, memory_message_id=None):
    if not has_column("user_account", "memory_summary"):
        return

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            fields = ["memory_summary=%s"]
            params = [memory_summary]
            guard_clause = ""
            if (
                memory_message_id is not None
                and has_column("user_account", "memory_message_id")
            ):
                fields.append("memory_message_id=%s")
                params.append(memory_message_id)
                guard_clause = (
                    " AND (memory_message_id IS NULL OR memory_message_id < %s)"
                )
            if has_column("user_account", "memory_updated_at"):
                fields.append("memory_updated_at=CURRENT_TIMESTAMP")
            params.append(user_id)
            if guard_clause:
                params.append(memory_message_id)

            cursor.execute(
                """
                UPDATE user_account
                SET {fields}
                WHERE id=%s{guard_clause}
                """.format(
                    fields=", ".join(fields),
                    guard_clause=guard_clause,
                ),
                tuple(params),
            )
    finally:
        conn.close()
