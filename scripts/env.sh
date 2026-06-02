#!/usr/bin/env bash

# Shared helpers for scripts in this repository. This file is meant to be sourced.

load_dotenv() {
  local env_file="${1:-.env}"
  if [ -f "$env_file" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
  fi
}

configure_vcpkg_defaults() {
  if [ -n "${CMAKE_TOOLCHAIN_FILE:-}" ]; then
    return 0
  fi

  local roots=()
  if [ -n "${VCPKG_ROOT:-}" ]; then
    roots+=("${VCPKG_ROOT}")
  fi
  if [ -n "${VCPKG_INSTALLATION_ROOT:-}" ]; then
    roots+=("${VCPKG_INSTALLATION_ROOT}")
  fi
  if command -v vcpkg >/dev/null 2>&1; then
    local vcpkg_exe
    vcpkg_exe="$(command -v vcpkg)"
    roots+=("$(cd "$(dirname "${vcpkg_exe}")" && pwd)")
  fi
  if [ -n "${HOME:-}" ]; then
    roots+=("${HOME}/vcpkg")
  fi
  roots+=("/opt/vcpkg" "/usr/local/vcpkg" "/root/vcpkg")

  local root toolchain
  for root in "${roots[@]}"; do
    [ -n "${root}" ] || continue
    toolchain="${root}/scripts/buildsystems/vcpkg.cmake"
    if [ -f "${toolchain}" ]; then
      export VCPKG_ROOT="${VCPKG_ROOT:-${root}}"
      export CMAKE_TOOLCHAIN_FILE="${toolchain}"
      if [ -x "${root}/vcpkg" ]; then
        case ":${PATH}:" in
          *":${root}:"*) ;;
          *) export PATH="${root}:${PATH}" ;;
        esac
      fi
      echo "[INFO] using vcpkg toolchain: ${CMAKE_TOOLCHAIN_FILE}"
      return 0
    fi
  done

  return 0
}

activate_python_env() {
  local env_name="$1"
  local venv_path="$2"
  local label="$3"

  if [ -n "${VIRTUAL_ENV:-}" ]; then
    if [ -z "$venv_path" ] || [ "${VIRTUAL_ENV}" = "$venv_path" ]; then
      echo "[INFO] ${label} using active virtualenv: ${VIRTUAL_ENV}"
      return 0
    fi
    echo "[INFO] ${label} active virtualenv differs; requested=${venv_path} active=${VIRTUAL_ENV}"
  fi

  if [ -n "${CONDA_DEFAULT_ENV:-}" ] && [ -n "$env_name" ] && [ "${CONDA_DEFAULT_ENV}" = "$env_name" ]; then
    echo "[INFO] ${label} using active conda env: ${CONDA_DEFAULT_ENV}"
    return 0
  fi

  if [ -n "$env_name" ]; then
    if command -v conda >/dev/null 2>&1; then
      local conda_base
      if conda_base="$(conda info --base 2>/dev/null)" && [ -f "${conda_base}/etc/profile.d/conda.sh" ]; then
        # shellcheck disable=SC1091
        source "${conda_base}/etc/profile.d/conda.sh"
        if conda activate "$env_name" >/dev/null 2>&1; then
          echo "[INFO] ${label} activated conda env: ${env_name}"
          return 0
        fi
        echo "[WARN] ${label} conda env not found: ${env_name}"
      else
        echo "[WARN] ${label} conda is unavailable"
      fi
    fi
  fi

  if [ -n "$venv_path" ] && [ -f "${venv_path}/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "${venv_path}/bin/activate"
    echo "[INFO] ${label} activated venv: ${venv_path}"
    return 0
  fi

  echo "[WARN] ${label} no Python environment activated; using python from PATH"
  return 0
}

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

build_gateway_auth_headers() {
  local key
  key="$(detect_gateway_api_key)"
  if [ -n "$key" ]; then
    printf '%s\n' "-H" "X-API-Key: ${key}"
  fi
}

json_read() {
  local expr="$1"
  python3 -c "import json,sys; data=json.load(sys.stdin); print(${expr})"
}

poll_gateway_task() {
  local base_url="$1"
  local task_id="$2"
  local label="$3"
  local max_rounds="${4:-90}"
  shift 4 || true
  local auth_headers=("$@")
  local status_url="${base_url}/v1/tasks/${task_id}"

  for _ in $(seq 1 "$max_rounds"); do
    local task_resp
    task_resp="$(curl -fsS "${auth_headers[@]}" "$status_url")"
    echo "$task_resp"

    local state
    state="$(printf "%s" "$task_resp" | json_read "data.get('data', data).get('state')")"
    if [ "$state" = "SUCCESS" ]; then
      echo "[OK] ${label} success"
      return 0
    fi
    if [ "$state" = "FAILURE" ] || [ "$state" = "FAILED" ]; then
      echo "[ERROR] ${label} failed" >&2
      return 1
    fi

    sleep 1
  done

  echo "[ERROR] timeout waiting ${label}" >&2
  return 1
}

poll_internal_task() {
  local base_url="$1"
  local task_id="$2"
  local label="$3"
  local max_rounds="${4:-60}"
  local status_url="${base_url}/internal/tasks/${task_id}"

  for _ in $(seq 1 "$max_rounds"); do
    local task_resp
    task_resp="$(curl -fsS "$status_url")"
    echo "$task_resp"

    local state
    state="$(printf "%s" "$task_resp" | json_read "data.get('data', data).get('state')")"
    if [ "$state" = "SUCCESS" ]; then
      echo "[OK] ${label} success"
      return 0
    fi
    if [ "$state" = "FAILURE" ] || [ "$state" = "FAILED" ]; then
      echo "[ERROR] ${label} failed" >&2
      return 1
    fi

    sleep 1
  done

  echo "[ERROR] timeout waiting ${label}" >&2
  return 1
}
