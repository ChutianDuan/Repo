#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${REPO_ROOT}/.run"
LOG_DIR="${REPO_ROOT}/logs"

cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a
  source ./.env
  set +a
fi

mkdir -p "$RUN_DIR" "$LOG_DIR"

ACTION="${1:-start}"
START_FRONTEND="${START_FRONTEND:-false}"
START_GATEWAY="${START_GATEWAY:-true}"
START_INIT_DB="${START_INIT_DB:-false}"

is_running() {
  local pid_file="$1"
  [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

start_service() {
  local name="$1"
  shift
  local pid_file="${RUN_DIR}/${name}.pid"
  local log_file="${LOG_DIR}/${name}.log"

  if is_running "$pid_file"; then
    echo "[SKIP] ${name} already running pid=$(cat "$pid_file")"
    return
  fi

  echo "[START] ${name} -> ${log_file}"
  nohup "$@" >"$log_file" 2>&1 &
  echo "$!" >"$pid_file"
}

stop_service() {
  local name="$1"
  local pid_file="${RUN_DIR}/${name}.pid"

  if ! is_running "$pid_file"; then
    rm -f "$pid_file"
    echo "[SKIP] ${name} not running"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  echo "[STOP] ${name} pid=${pid}"
  kill "$pid" 2>/dev/null || true
  rm -f "$pid_file"
}

status_service() {
  local name="$1"
  local pid_file="${RUN_DIR}/${name}.pid"

  if is_running "$pid_file"; then
    echo "[OK] ${name} running pid=$(cat "$pid_file")"
  else
    echo "[--] ${name} stopped"
  fi
}

ensure_gateway_binary() {
  if [ "${START_GATEWAY}" != "true" ]; then
    return
  fi

  if [ -x "${REPO_ROOT}/cpp_gateway/build/cpp_gateway" ]; then
    return
  fi

  if ! command -v cmake >/dev/null 2>&1; then
    echo "[ERROR] cpp_gateway/build/cpp_gateway not found and cmake is unavailable"
    exit 1
  fi

  echo "[BUILD] cpp_gateway"
  local cmake_args=()
  if [ -n "${CMAKE_TOOLCHAIN_FILE:-}" ]; then
    cmake_args+=("-DCMAKE_TOOLCHAIN_FILE=${CMAKE_TOOLCHAIN_FILE}")
  fi
  if [ -n "${Drogon_DIR:-}" ]; then
    cmake_args+=("-DDrogon_DIR=${Drogon_DIR}")
  fi
  cmake -S cpp_gateway -B cpp_gateway/build -DCMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE:-Debug}" "${cmake_args[@]}"
  cmake --build cpp_gateway/build -j "${BUILD_JOBS:-4}"
}

start_all() {
  if [ "${START_INIT_DB}" = "true" ]; then
    bash scripts/init_db.sh
  fi

  ensure_gateway_binary
  start_service api bash scripts/start_api.sh
  start_service worker bash scripts/start_worker.sh

  if [ "${START_GATEWAY}" = "true" ]; then
    start_service gateway bash cpp_gateway/scripts/start_gateway.sh
  fi

  if [ "${START_FRONTEND}" = "true" ]; then
    start_service frontend bash -lc "cd frontend && npm run dev -- --host 0.0.0.0"
  fi

  echo "[DONE] stack start requested"
  echo "       API:     http://127.0.0.1:${APP_PORT:-8000}/internal/health"
  echo "       Gateway: ${GATEWAY_BASE_URL:-http://127.0.0.1:8080}/health"
  echo "       E2E:     bash scripts/e2e_all.sh"
}

stop_all() {
  stop_service frontend
  stop_service gateway
  stop_service worker
  stop_service api
}

case "$ACTION" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    status_service api
    status_service worker
    status_service gateway
    status_service frontend
    ;;
  e2e)
    bash scripts/e2e_all.sh
    ;;
  *)
    echo "Usage: $0 [start|stop|restart|status|e2e]"
    exit 1
    ;;
esac
