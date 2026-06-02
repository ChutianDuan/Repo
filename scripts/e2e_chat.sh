#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

source "${REPO_ROOT}/scripts/env.sh"
load_dotenv "${REPO_ROOT}/.env"

PYTHON_BASE_URL="${PYTHON_BASE_URL:-http://127.0.0.1:8000}"
GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://127.0.0.1:8080}"
TEST_FILE="${1:-./day7_demo.md}"
USER_ID="${USER_ID:-1}"
TOP_K="${TOP_K:-3}"
QUERY_TEXT="${QUERY_TEXT:-这份文档讲了什么？}"

if [ ! -f "$TEST_FILE" ]; then
  echo "[ERROR] file not found: $TEST_FILE" >&2
  exit 1
fi

mapfile -t AUTH_HEADERS < <(build_gateway_auth_headers)

section() {
  echo "============================================================"
  echo "$1"
}

section "[1/7] upload document to python internal"
UPLOAD_RESP="$(curl -fsS -X POST "${PYTHON_BASE_URL}/internal/documents/upload" \
  -F "user_id=${USER_ID}" \
  -F "file=@${TEST_FILE}")"
echo "$UPLOAD_RESP"
DOC_ID="$(printf "%s" "$UPLOAD_RESP" | json_read "data.get('data', data)['doc_id']")"
echo "[INFO] doc_id=${DOC_ID}"

section "[2/7] submit ingest job"
INGEST_RESP="$(curl -fsS -X POST "${PYTHON_BASE_URL}/internal/jobs/ingest" \
  -H "Content-Type: application/json" \
  -d "{\"doc_id\": ${DOC_ID}}")"
echo "$INGEST_RESP"
INGEST_TASK_ID="$(printf "%s" "$INGEST_RESP" | json_read "data.get('data', data)['task_id']")"
echo "[INFO] ingest_task_id=${INGEST_TASK_ID}"

section "[3/7] wait ingest success"
poll_internal_task "$PYTHON_BASE_URL" "$INGEST_TASK_ID" "ingest" 60

section "[4/7] create session via gateway"
SESSION_RESP="$(curl -fsS -X POST "${GATEWAY_BASE_URL}/v1/sessions" \
  "${AUTH_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":${USER_ID},\"title\":\"Day7 E2E Demo Session\"}")"
echo "$SESSION_RESP"
SESSION_ID="$(printf "%s" "$SESSION_RESP" | json_read "data['data']['session_id']")"
echo "[INFO] session_id=${SESSION_ID}"

section "[5/7] submit user message via gateway"
CHAT_RESP="$(curl -fsS -X POST "${GATEWAY_BASE_URL}/v1/sessions/${SESSION_ID}/messages" \
  "${AUTH_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"${QUERY_TEXT}\",\"top_k\":${TOP_K}}")"
echo "$CHAT_RESP"
CHAT_TASK_ID="$(printf "%s" "$CHAT_RESP" | json_read "data['data']['task_id']")"
USER_MESSAGE_ID="$(printf "%s" "$CHAT_RESP" | json_read "data['data']['message_id']")"
echo "[INFO] user_message_id=${USER_MESSAGE_ID}"
echo "[INFO] chat_task_id=${CHAT_TASK_ID}"

section "[6/7] wait chat success"
poll_internal_task "$PYTHON_BASE_URL" "$CHAT_TASK_ID" "chat" 60

section "[7/7] list messages via gateway"
MESSAGES_RESP="$(curl -fsS "${AUTH_HEADERS[@]}" "${GATEWAY_BASE_URL}/v1/sessions/${SESSION_ID}/messages")"
echo "$MESSAGES_RESP"

echo "============================================================"
echo "[DONE] end-to-end chat flow succeeded"
