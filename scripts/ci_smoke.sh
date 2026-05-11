#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! python3 -c "import pytest" >/dev/null 2>&1; then
  echo "[ERROR] pytest is not installed. Run: pip install -r python_rag/requirements-dev.txt" >&2
  exit 1
fi

python3 -m compileall python_rag
python3 -m pytest tests

bash -n scripts/init_db.sh
bash -n scripts/start_api.sh
bash -n scripts/start_worker.sh
bash -n scripts/start_vllm.sh
bash -n scripts/start_all.sh
bash -n cpp_gateway/scripts/start_gateway.sh

if command -v npm >/dev/null 2>&1; then
  (cd frontend && npm run build)
else
  echo "[WARN] npm is not installed; skipping frontend build"
fi
