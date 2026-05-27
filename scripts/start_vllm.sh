#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

source "${REPO_ROOT}/scripts/env.sh"
load_dotenv "${REPO_ROOT}/.env"

LLM_RUNTIME="${LLM_RUNTIME:-api}"

case "${LLM_RUNTIME}" in
  api|remote|openai_compatible)
    LLM_BASE_URL="${LLM_BASE_URL:-}"
    LLM_MODEL="${LLM_MODEL:-}"
    LLM_API_KEY="${MIMO_API_KEY:-${LLM_API_KEY:-}}"
    LLM_API_CHECK="${LLM_API_CHECK:-true}"
    LLM_API_CHECK_STRICT="${LLM_API_CHECK_STRICT:-false}"

    if [ -z "${LLM_BASE_URL}" ]; then
      echo "[ERROR] LLM_BASE_URL is required for API mode" >&2
      exit 1
    fi
    if [ -z "${LLM_MODEL}" ]; then
      echo "[ERROR] LLM_MODEL is required for API mode" >&2
      exit 1
    fi

    echo "[INFO] LLM runtime=api"
    echo "[INFO] LLM endpoint=${LLM_BASE_URL}"
    echo "[INFO] LLM model=${LLM_MODEL}"
    echo "[INFO] local vLLM will not be started"

    if [ "${LLM_API_CHECK}" = "true" ] || [ "${LLM_API_CHECK}" = "1" ]; then
      if ! command -v curl >/dev/null 2>&1; then
        echo "[WARN] curl is unavailable; skipping LLM API check" >&2
        exit 0
      fi

      headers=()
      if [ -n "${LLM_API_KEY}" ]; then
        headers+=("-H" "Authorization: Bearer ${LLM_API_KEY}")
      fi

      if curl -fsS "${headers[@]}" "${LLM_BASE_URL%/}/models" >/dev/null; then
        echo "[OK] LLM API /models reachable"
      else
        message="LLM API /models check failed; verify LLM_BASE_URL, LLM_API_KEY/MIMO_API_KEY and provider compatibility"
        if [ "${LLM_API_CHECK_STRICT}" = "true" ] || [ "${LLM_API_CHECK_STRICT}" = "1" ]; then
          echo "[ERROR] ${message}" >&2
          exit 1
        fi
        echo "[WARN] ${message}" >&2
      fi
    fi
    exit 0
    ;;
  local|local_vllm|vllm)
    ;;
  *)
    echo "[ERROR] unsupported LLM_RUNTIME=${LLM_RUNTIME}; use api or local_vllm" >&2
    exit 1
    ;;
esac

activate_python_env "${VLLM_ENV:-vllm-qwen3}" "${VLLM_VENV:-}" "vllm"

VLLM_MODEL_PATH="${VLLM_MODEL_PATH:-}"
VLLM_SERVED_MODEL_NAME="${VLLM_SERVED_MODEL_NAME:-}"
VLLM_HOST="${VLLM_HOST:-0.0.0.0}"
VLLM_PORT="${VLLM_PORT:-9000}"
VLLM_API_KEY="${VLLM_API_KEY:-}"
VLLM_CUDA_VISIBLE_DEVICES="${VLLM_CUDA_VISIBLE_DEVICES:-}"
VLLM_DTYPE="${VLLM_DTYPE:-auto}"
VLLM_TENSOR_PARALLEL_SIZE="${VLLM_TENSOR_PARALLEL_SIZE:-1}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.9}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-}"

if [ -z "$VLLM_MODEL_PATH" ]; then
  echo "VLLM_MODEL_PATH is required" >&2
  exit 1
fi

if [ -z "$VLLM_SERVED_MODEL_NAME" ]; then
  VLLM_SERVED_MODEL_NAME="$VLLM_MODEL_PATH"
fi

if [ -n "$VLLM_CUDA_VISIBLE_DEVICES" ]; then
  export CUDA_VISIBLE_DEVICES="$VLLM_CUDA_VISIBLE_DEVICES"
fi

echo "[INFO] vllm model=${VLLM_MODEL_PATH}"
echo "[INFO] vllm served_model=${VLLM_SERVED_MODEL_NAME}"
echo "[INFO] vllm listen=http://${VLLM_HOST}:${VLLM_PORT}"
echo "[INFO] vllm CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES-<unset>}"

CMD=(
  vllm serve "$VLLM_MODEL_PATH"
  --host "$VLLM_HOST"
  --port "$VLLM_PORT"
  --served-model-name "$VLLM_SERVED_MODEL_NAME"
  --dtype "$VLLM_DTYPE"
  --tensor-parallel-size "$VLLM_TENSOR_PARALLEL_SIZE"
  --gpu-memory-utilization "$VLLM_GPU_MEMORY_UTILIZATION"
  --generation-config vllm
)

if [ -n "$VLLM_API_KEY" ]; then
  CMD+=(--api-key "$VLLM_API_KEY")
fi

if [ -n "$VLLM_MAX_MODEL_LEN" ]; then
  CMD+=(--max-model-len "$VLLM_MAX_MODEL_LEN")
fi

exec "${CMD[@]}"
