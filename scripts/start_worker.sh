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
celery -A python_rag.modules.tasks.celery_app worker -l INFO
