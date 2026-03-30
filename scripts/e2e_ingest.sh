#!/usr/bin/env bash
set -euo pipefail

GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://127.0.0.1:8080}"
TEST_FILE="${1:-./test.md}"

if [ ! -f "$TEST_FILE" ]; then
  echo "[ERROR] file not found: $TEST_FILE"
  exit 1
fi

echo "==> upload document"
UPLOAD_RESP=$(curl -s -X POST "${GATEWAY_BASE_URL}/v1/documents" \
  -F "user_id=1" \
  -F "file=@${TEST_FILE}")

echo "$UPLOAD_RESP"

DOC_ID=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['doc_id'])")
DB_TASK_ID=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['db_task_id'])")

echo "doc_id=$DOC_ID"
echo "db_task_id=$DB_TASK_ID"

echo "==> poll task"
for i in $(seq 1 20); do
  TASK_RESP=$(curl -s "${GATEWAY_BASE_URL}/v1/tasks/${DB_TASK_ID}")
  echo "$TASK_RESP"

  STATE=$(echo "$TASK_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")

  if [ "$STATE" = "SUCCESS" ]; then
    echo "[OK] ingest success"
    exit 0
  fi

  if [ "$STATE" = "FAILURE" ]; then
    echo "[ERROR] ingest failed"
    exit 1
  fi

  sleep 1
done

echo "[ERROR] timeout waiting task finish"
exit 1