#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/ubuntu/Repo"

cd "$REPO_ROOT"

python3 -m uvicorn python_rag.app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
