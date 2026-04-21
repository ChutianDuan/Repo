#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${GATEWAY_DIR}/.." && pwd)"

cd "${GATEWAY_DIR}"

if [ -f "${REPO_ROOT}/.env" ]; then
  set -a
  source "${REPO_ROOT}/.env"
  set +a
fi

export REPO_ROOT
export PYTHON_INTERNAL_BASE_URL="${PYTHON_INTERNAL_BASE_URL:-http://127.0.0.1:8000}"
exec ./build/cpp_gateway
