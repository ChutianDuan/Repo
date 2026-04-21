#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a
  source ./.env
  set +a
fi

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
