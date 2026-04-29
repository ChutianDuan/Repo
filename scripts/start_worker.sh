#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a
  source ./.env
  set +a
fi

case "${PYTHON_DISABLE_CUDA:-false}" in
  true|1|yes|on)
    export CUDA_VISIBLE_DEVICES=""
    ;;
  *)
    if [ -n "${PYTHON_CUDA_VISIBLE_DEVICES:-}" ]; then
      export CUDA_VISIBLE_DEVICES="$PYTHON_CUDA_VISIBLE_DEVICES"
    fi
    ;;
esac

export PYTHONPATH="$REPO_ROOT"

CELERY_POOL="${CELERY_POOL:-threads}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-4}"

celery -A python_rag.modules.tasks.celery_app worker \
  -l INFO \
  --pool "${CELERY_POOL}" \
  --concurrency "${CELERY_CONCURRENCY}"
