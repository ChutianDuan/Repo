#!/usr/bin/env bash
set -euo pipefail

PYTHON_BASE_URL="${PYTHON_BASE_URL:-http://127.0.0.1:8000}"
GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://127.0.0.1:8080}"
TEST_FILE="${1:-./day7_demo.md}"
USER_ID="${USER_ID:-1}"
TOP_K="${TOP_K:-3}"
QUERY_TEXT="${QUERY_TEXT:-这份文档讲了什么？}"

if [ ! -f "$TEST_FILE" ]; then
  echo "[ERROR] file not found: $TEST_FILE"
  exit 1
fi

echo "============================================================"
echo "[1/7] upload document to python internal"
UPLOAD_RESP=$(curl -s -X POST "${PYTHON_BASE_URL}/internal/documents/upload" \
  -F "user_id=${USER_ID}" \
  -F "file=@${TEST_FILE}")

echo "$UPLOAD_RESP"

DOC_ID=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['doc_id'])")
echo "[INFO] doc_id=${DOC_ID}"

echo "============================================================"
echo "[2/7] submit ingest job"
INGEST_RESP=$(curl -s -X POST "${PYTHON_BASE_URL}/internal/jobs/ingest" \
  -H "Content-Type: application/json" \
  -d "{\"doc_id\": ${DOC_ID}}")

echo "$INGEST_RESP"

INGEST_TASK_ID=$(echo "$INGEST_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
echo "[INFO] ingest_task_id=${INGEST_TASK_ID}"

echo "============================================================"
echo "[3/7] wait ingest success"
for i in $(seq 1 60); do
  TASK_RESP=$(curl -s "${PYTHON_BASE_URL}/internal/tasks/${INGEST_TASK_ID}")
  echo "$TASK_RESP"

  STATE=$(echo "$TASK_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")

  if [ "$STATE" = "SUCCESS" ]; then
    echo "[OK] ingest success"
    break
  fi

  if [ "$STATE" = "FAILURE" ]; then
    echo "[ERROR] ingest failed"
    exit 1
  fi

  sleep 1
done

echo "============================================================"
echo "[4/7] create session via gateway"
SESSION_RESP=$(curl -s -X POST "${GATEWAY_BASE_URL}/v1/sessions" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": ${USER_ID},
    \"title\": \"Day7 E2E Demo Session\"
  }")

echo "$SESSION_RESP"

SESSION_ID=$(echo "$SESSION_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['session_id'])")
echo "[INFO] session_id=${SESSION_ID}"

echo "============================================================"
echo "[5/7] submit user message via gateway"
CHAT_RESP=$(curl -s -X POST "${GATEWAY_BASE_URL}/v1/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d "{
    \"doc_id\": ${DOC_ID},
    \"content\": \"${QUERY_TEXT}\",
    \"top_k\": ${TOP_K}
  }")

echo "$CHAT_RESP"

CHAT_TASK_ID=$(echo "$CHAT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")
USER_MESSAGE_ID=$(echo "$CHAT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['message_id'])")
echo "[INFO] user_message_id=${USER_MESSAGE_ID}"
echo "[INFO] chat_task_id=${CHAT_TASK_ID}"

echo "============================================================"
echo "[6/7] wait chat success"
for i in $(seq 1 60); do
  TASK_RESP=$(curl -s "${PYTHON_BASE_URL}/internal/tasks/${CHAT_TASK_ID}")
  echo "$TASK_RESP"

  STATE=$(echo "$TASK_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")

  if [ "$STATE" = "SUCCESS" ]; then
    echo "[OK] chat success"
    break
  fi

  if [ "$STATE" = "FAILURE" ]; then
    echo "[ERROR] chat failed"
    exit 1
  fi

  sleep 1
done

echo "============================================================"
echo "[7/7] list messages via gateway"
MESSAGES_RESP=$(curl -s "${GATEWAY_BASE_URL}/v1/sessions/${SESSION_ID}/messages")
echo "$MESSAGES_RESP"

echo "============================================================"
echo "[DONE] end-to-end chat flow succeeded"