#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=scripts/env.sh
source "${REPO_ROOT}/scripts/env.sh"
load_dotenv "${REPO_ROOT}/.env"
activate_python_env \
  "${RAG_API_ENV:-rag-api}" \
  "${RAG_API_VENV:-${REPO_ROOT}/.venv}" \
  "test"

if ! python3 -c "import pytest" >/dev/null 2>&1; then
  echo "[ERROR] pytest is not installed in the active Python environment" >&2
  echo "        Run: pip install -r python_rag/requirements-dev.txt" >&2
  exit 1
fi

python3 -m compileall python_rag tests scripts
python3 -m pytest tests

for script in scripts/*.sh cpp_gateway/scripts/*.sh; do
  [ -f "$script" ] || continue
  bash -n "$script"
done

if command -v npm >/dev/null 2>&1; then
  (cd frontend && npm run build)
else
  echo "[WARN] npm is not installed; skipping frontend build"
fi
