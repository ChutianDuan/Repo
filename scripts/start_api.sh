#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

source "${REPO_ROOT}/scripts/env.sh"
load_dotenv "${REPO_ROOT}/.env"
activate_python_env "${RAG_API_ENV:-rag-api}" "${RAG_API_VENV:-${REPO_ROOT}/.venv}" "api"

API_DISABLE_CUDA="${API_DISABLE_CUDA:-${PYTHON_DISABLE_CUDA:-false}}"
API_CUDA_VISIBLE_DEVICES="${API_CUDA_VISIBLE_DEVICES:-${PYTHON_CUDA_VISIBLE_DEVICES:-}}"

case "$API_DISABLE_CUDA" in
  true|1|yes|on)
    export CUDA_VISIBLE_DEVICES=""
    ;;
  *)
    if [ -n "$API_CUDA_VISIBLE_DEVICES" ]; then
      export CUDA_VISIBLE_DEVICES="$API_CUDA_VISIBLE_DEVICES"
    fi
    ;;
esac

export PYTHONPATH="$REPO_ROOT"

APP_RELOAD="${APP_RELOAD:-false}"

echo "[INFO] api CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES-<unset>}"

UVICORN_ARGS=(
  python3 -m uvicorn python_rag.app.main:app
  --host "${APP_HOST:-0.0.0.0}"
  --port "${APP_PORT:-8000}"
)

if [ "${APP_RELOAD}" = "true" ]; then
  UVICORN_ARGS+=(--reload)
fi

exec "${UVICORN_ARGS[@]}"
