#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a
  source ./.env
  set +a
fi

GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://127.0.0.1:8080}"
TEST_FILE="${1:-./day7_demo.md}"

detect_gateway_api_key() {
  if [ -n "${GATEWAY_API_KEY:-}" ]; then
    printf "%s" "$GATEWAY_API_KEY"
    return
  fi

  local configured_keys="${GATEWAY_API_KEYS:-}"
  local first_entry="${configured_keys%%,*}"
  if [ -z "${first_entry:-}" ]; then
    return
  fi

  if [[ "$first_entry" == *"="* ]]; then
    printf "%s" "${first_entry#*=}"
    return
  fi
  if [[ "$first_entry" == *":"* ]]; then
    printf "%s" "${first_entry#*:}"
    return
  fi
  printf "%s" "$first_entry"
}

GATEWAY_API_KEY_VALUE="$(detect_gateway_api_key)"
AUTH_HEADERS=()
if [ -n "$GATEWAY_API_KEY_VALUE" ]; then
  AUTH_HEADERS=(-H "X-API-Key: ${GATEWAY_API_KEY_VALUE}")
fi

if [ ! -f "$TEST_FILE" ]; then
  echo "[ERROR] file not found: $TEST_FILE"
  exit 1
fi

echo "==> upload document"
UPLOAD_RESP=$(curl -s -X POST "${GATEWAY_BASE_URL}/v1/documents" \
  "${AUTH_HEADERS[@]}" \
  -F "user_id=1" \
  -F "file=@${TEST_FILE}")

echo "$UPLOAD_RESP"

DOC_ID=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['doc_id'])")
TASK_ID=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

echo "doc_id=$DOC_ID"
echo "task_id=$TASK_ID"

echo "==> poll task"
for i in $(seq 1 20); do
  TASK_RESP=$(curl -s "${AUTH_HEADERS[@]}" "${GATEWAY_BASE_URL}/v1/tasks/${TASK_ID}")
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
