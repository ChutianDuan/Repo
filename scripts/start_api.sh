#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a
  source ./.env
  set +a
fi

export PYTHONPATH="$REPO_ROOT"

APP_RELOAD="${APP_RELOAD:-false}"

UVICORN_ARGS=(
  python3 -m uvicorn python_rag.app.main:app
  --host "${APP_HOST:-0.0.0.0}"
  --port "${APP_PORT:-8000}"
)

if [ "${APP_RELOAD}" = "true" ]; then
  UVICORN_ARGS+=(--reload)
fi

exec "${UVICORN_ARGS[@]}"
