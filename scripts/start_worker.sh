#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

source "${REPO_ROOT}/scripts/env.sh"
load_dotenv "${REPO_ROOT}/.env"
activate_python_env "${RAG_API_ENV:-rag-api}" "${RAG_API_VENV:-${REPO_ROOT}/.venv}" "worker"

WORKER_DISABLE_CUDA="${WORKER_DISABLE_CUDA:-${PYTHON_DISABLE_CUDA:-false}}"
WORKER_CUDA_VISIBLE_DEVICES="${WORKER_CUDA_VISIBLE_DEVICES:-${PYTHON_CUDA_VISIBLE_DEVICES:-}}"

case "$WORKER_DISABLE_CUDA" in
  true|1|yes|on)
    export CUDA_VISIBLE_DEVICES=""
    ;;
  *)
    if [ -n "$WORKER_CUDA_VISIBLE_DEVICES" ]; then
      export CUDA_VISIBLE_DEVICES="$WORKER_CUDA_VISIBLE_DEVICES"
    fi
    ;;
esac

export PYTHONPATH="$REPO_ROOT"

CELERY_POOL="${CELERY_POOL:-threads}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-4}"

echo "[INFO] worker CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES-<unset>}"

celery -A python_rag.modules.tasks.celery_app worker \
  -l INFO \
  --pool "${CELERY_POOL}" \
  --concurrency "${CELERY_CONCURRENCY}"
