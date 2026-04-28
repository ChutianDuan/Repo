#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a
  source ./.env
  set +a
fi

PYTHON_BASE_URL="${PYTHON_BASE_URL:-http://127.0.0.1:8000}"
GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://127.0.0.1:8080}"
TEST_FILE="${1:-./day7_demo.md}"
TOP_K="${TOP_K:-3}"
QUERY_TEXT="${QUERY_TEXT:-这份文档讲了什么？}"

if [ ! -f "$TEST_FILE" ]; then
  echo "[ERROR] file not found: $TEST_FILE"
  exit 1
fi

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

json_read() {
  local expr="$1"
  python3 -c "import json,sys; data=json.load(sys.stdin); print(${expr})"
}

poll_task() {
  local task_id="$1"
  local label="$2"
  local status_url="${GATEWAY_BASE_URL}/v1/tasks/${task_id}"

  for _ in $(seq 1 90); do
    local task_resp
    task_resp="$(curl -fsS "${AUTH_HEADERS[@]}" "$status_url")"
    echo "$task_resp"

    local state
    state="$(printf "%s" "$task_resp" | json_read "data.get('state')")"
    if [ "$state" = "SUCCESS" ]; then
      echo "[OK] ${label} success"
      return
    fi
    if [ "$state" = "FAILURE" ] || [ "$state" = "FAILED" ]; then
      echo "[ERROR] ${label} failed"
      exit 1
    fi

    sleep 1
  done

  echo "[ERROR] timeout waiting ${label}"
  exit 1
}

echo "============================================================"
echo "[1/7] create e2e user"
USERNAME="e2e_$(date +%Y%m%d_%H%M%S)_$$"
USER_RESP="$(curl -fsS -X POST "${GATEWAY_BASE_URL}/v1/users" \
  "${AUTH_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${USERNAME}\"}")"
echo "$USER_RESP"
USER_ID="$(printf "%s" "$USER_RESP" | json_read "data['data']['id']")"
echo "[INFO] user_id=${USER_ID}"

echo "============================================================"
echo "[2/7] upload document via gateway"
UPLOAD_RESP="$(curl -fsS -X POST "${GATEWAY_BASE_URL}/v1/documents" \
  "${AUTH_HEADERS[@]}" \
  -F "user_id=${USER_ID}" \
  -F "file=@${TEST_FILE}")"
echo "$UPLOAD_RESP"
DOC_ID="$(printf "%s" "$UPLOAD_RESP" | json_read "data['doc_id']")"
INGEST_TASK_ID="$(printf "%s" "$UPLOAD_RESP" | json_read "data['task_id']")"
echo "[INFO] doc_id=${DOC_ID}"
echo "[INFO] ingest_task_id=${INGEST_TASK_ID}"

echo "============================================================"
echo "[3/7] wait ingest"
poll_task "$INGEST_TASK_ID" "ingest"

echo "============================================================"
echo "[4/7] create session"
SESSION_RESP="$(curl -fsS -X POST "${GATEWAY_BASE_URL}/v1/sessions" \
  "${AUTH_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":${USER_ID},\"title\":\"E2E Session ${USERNAME}\"}")"
echo "$SESSION_RESP"
SESSION_ID="$(printf "%s" "$SESSION_RESP" | json_read "data['data']['session_id']")"
echo "[INFO] session_id=${SESSION_ID}"

echo "============================================================"
echo "[5/7] submit chat"
CHAT_RESP="$(curl -fsS -X POST "${GATEWAY_BASE_URL}/v1/sessions/${SESSION_ID}/messages" \
  "${AUTH_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"doc_id\":${DOC_ID},\"content\":\"${QUERY_TEXT}\",\"top_k\":${TOP_K}}")"
echo "$CHAT_RESP"
CHAT_TASK_ID="$(printf "%s" "$CHAT_RESP" | json_read "data['data']['task_id']")"
echo "[INFO] chat_task_id=${CHAT_TASK_ID}"

echo "============================================================"
echo "[6/7] wait chat and inspect messages"
poll_task "$CHAT_TASK_ID" "chat"
MESSAGES_RESP="$(curl -fsS "${AUTH_HEADERS[@]}" "${GATEWAY_BASE_URL}/v1/sessions/${SESSION_ID}/messages")"
echo "$MESSAGES_RESP"

FIRST_CHUNK_ID="$(printf "%s" "$MESSAGES_RESP" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
messages = (payload.get("data") or {}).get("items") or []
for message in messages:
    for citation in message.get("citations") or []:
        chunk_id = citation.get("chunk_id")
        if chunk_id:
            print(chunk_id)
            raise SystemExit(0)
print("")
')"

if [ -n "$FIRST_CHUNK_ID" ]; then
  echo "[INFO] run retrieval eval with relevant_chunk_id=${FIRST_CHUNK_ID}"
  curl -fsS -X POST "${PYTHON_BASE_URL}/internal/search" \
    -H "Content-Type: application/json" \
    -d "{\"doc_id\":${DOC_ID},\"query\":\"${QUERY_TEXT}\",\"top_k\":${TOP_K},\"relevant_chunk_ids\":[${FIRST_CHUNK_ID}]}"
  echo
fi

echo "============================================================"
echo "[7/7] monitor overview"
curl -fsS "${AUTH_HEADERS[@]}" "${GATEWAY_BASE_URL}/v1/monitor/overview"
echo
echo "[DONE] end-to-end flow succeeded"
