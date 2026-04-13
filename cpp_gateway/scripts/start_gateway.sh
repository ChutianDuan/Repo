#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${GATEWAY_DIR}"

export PYTHON_INTERNAL_BASE_URL="${PYTHON_INTERNAL_BASE_URL:-http://127.0.0.1:8000}"
exec ./build/cpp_gateway
