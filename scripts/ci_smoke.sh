#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEST_CONDA_ENV="${RAG_API_ENV:-rag-api}"

# shellcheck source=scripts/env.sh
source "${REPO_ROOT}/scripts/env.sh"
activate_python_env "${TEST_CONDA_ENV}" "" "test"
if [ "${CONDA_DEFAULT_ENV:-}" != "${TEST_CONDA_ENV}" ]; then
  echo "[ERROR] tests require conda env: ${TEST_CONDA_ENV}. Run: conda activate ${TEST_CONDA_ENV}" >&2
  exit 1
fi

if ! python3 -c "import pytest" >/dev/null 2>&1; then
  echo "[ERROR] pytest is not installed. Run: pip install -r python_rag/requirements-dev.txt" >&2
  exit 1
fi

python3 -m compileall python_rag
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
