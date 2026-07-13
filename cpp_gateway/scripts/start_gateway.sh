#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${GATEWAY_DIR}/.." && pwd)"

cd "${GATEWAY_DIR}"

source "${REPO_ROOT}/scripts/env.sh"
load_dotenv "${REPO_ROOT}/.env"

export REPO_ROOT
export PYTHON_INTERNAL_BASE_URL="${PYTHON_INTERNAL_BASE_URL:-http://127.0.0.1:8000}"

if [ ! -x "./build/cpp_gateway" ]; then
  echo "[ERROR] gateway binary not found: ${GATEWAY_DIR}/build/cpp_gateway" >&2
  echo "        Run: cmake -S cpp_gateway -B cpp_gateway/build && cmake --build cpp_gateway/build" >&2
  exit 1
fi

exec ./build/cpp_gateway
