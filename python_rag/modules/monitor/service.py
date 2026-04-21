import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from python_rag.config import LLM_BASE_URL, LLM_ENABLE, STORAGE_ROOT
from python_rag.infra.mysql import get_mysql_connection
from python_rag.infra.redis_client import get_redis_client
from python_rag.modules.tasks.celery_app import celery_app


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _service_state(ok: Optional[bool]) -> str:
    if ok is True:
        return "ok"
    if ok is False:
        return "error"
    return "unknown"


def _get_system_metrics() -> Dict[str, Optional[float]]:
    try:
        import psutil
    except Exception:
        return {
            "cpu_percent": None,
            "memory_percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "disk_percent": None,
            "network_rx_kbps": None,
            "network_tx_kbps": None,
        }

    memory = psutil.virtual_memory()
    disk_path = STORAGE_ROOT if os.path.exists(STORAGE_ROOT) else os.getcwd()
    disk = psutil.disk_usage(disk_path)

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.05),
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024 ** 3), 2),
        "memory_total_gb": round(memory.total / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "network_rx_kbps": None,
        "network_tx_kbps": None,
    }


def _get_gpu_metrics() -> List[Dict[str, Any]]:
    if not shutil.which("nvidia-smi"):
        return []

    command = [
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=2)
    except Exception:
        return []

    gpus = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 6:
            continue
        gpus.append({
            "id": int(_safe_float(parts[0]) or 0),
            "name": parts[1],
            "util_percent": _safe_float(parts[2]),
            "memory_used_mb": _safe_float(parts[3]),
            "memory_total_mb": _safe_float(parts[4]),
            "temperature": _safe_float(parts[5]),
        })
    return gpus


def _mysql_ok() -> bool:
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS ok")
            row = cursor.fetchone()
            return row and row["ok"] == 1
    finally:
        conn.close()


def _redis_ok() -> bool:
    client = get_redis_client()
    return bool(client.ping())


def _worker_ok() -> bool:
    try:
        replies = celery_app.control.ping(timeout=0.5)
        return len(replies) > 0
    except Exception:
        return False


def _query_dashboard_counts() -> Dict[str, Any]:
    result = {
        "queue": {"pending": 0, "running": 0, "failed": 0},
        "rag": {"documents_ready": 0, "total_chunks": 0},
    }

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    SUM(state='PENDING') AS pending,
                    SUM(state IN ('STARTED', 'PROGRESS')) AS running,
                    SUM(state IN ('FAILURE', 'FAILED')) AS failed
                FROM tasks
                """
            )
            task_row = cursor.fetchone() or {}
            result["queue"] = {
                "pending": int(task_row.get("pending") or 0),
                "running": int(task_row.get("running") or 0),
                "failed": int(task_row.get("failed") or 0),
            }

            cursor.execute(
                """
                SELECT
                    SUM(status='READY') AS documents_ready,
                    COUNT(c.id) AS total_chunks
                FROM documents d
                LEFT JOIN doc_chunks c ON c.doc_id = d.id
                """
            )
            rag_row = cursor.fetchone() or {}
            result["rag"] = {
                "documents_ready": int(rag_row.get("documents_ready") or 0),
                "total_chunks": int(rag_row.get("total_chunks") or 0),
            }
    finally:
        conn.close()

    return result


def get_monitor_overview() -> Dict[str, Any]:
    started_at = time.perf_counter()
    mysql_ok: Optional[bool] = None
    redis_ok: Optional[bool] = None
    worker_ok: Optional[bool] = None

    try:
        mysql_ok = _mysql_ok()
    except Exception:
        mysql_ok = False

    try:
        redis_ok = _redis_ok()
    except Exception:
        redis_ok = False

    try:
        worker_ok = _worker_ok()
    except Exception:
        worker_ok = False

    try:
        counts = _query_dashboard_counts() if mysql_ok else {
            "queue": {"pending": 0, "running": 0, "failed": 0},
            "rag": {"documents_ready": 0, "total_chunks": 0},
        }
    except Exception:
        counts = {
            "queue": {"pending": 0, "running": 0, "failed": 0},
            "rag": {"documents_ready": 0, "total_chunks": 0},
        }

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    llm_state = "ok" if LLM_ENABLE and LLM_BASE_URL else "unknown"

    return {
        "system": _get_system_metrics(),
        "gpu": _get_gpu_metrics(),
        "services": {
            "mysql": _service_state(mysql_ok),
            "redis": _service_state(redis_ok),
            "worker": _service_state(worker_ok),
            "llm": llm_state,
            "embedding": "unknown",
            "api": "ok",
        },
        "queue": counts["queue"],
        "latency": {
            "api_ms": latency_ms,
            "chat_ms": None,
            "retrieval_ms": None,
        },
        "rag": counts["rag"],
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
