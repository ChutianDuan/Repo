#!/usr/bin/env bash
set -e

export PYTHON_INTERNAL_BASE_URL="${PYTHON_INTERNAL_BASE_URL:-http://127.0.0.1:8000}"
../build/cpp_gateway