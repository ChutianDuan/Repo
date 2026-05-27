# Scripts

This directory keeps operational scripts for local development, smoke checks, and E2E validation. Public entrypoints are kept stable so README commands continue to work.

## Start and Stop

- `start_all.sh [start|stop|restart|status|e2e]`: unified local stack manager. Starts API, worker, gateway, and optionally frontend.
- `start_api.sh`: starts the FastAPI internal service.
- `start_worker.sh`: starts the Celery worker.
- `start_vllm.sh`: checks remote OpenAI-compatible API by default; starts local vLLM only with `LLM_RUNTIME=local_vllm`.
- `init_db.sh`: creates/updates the MySQL schema.

Useful variables:

- `START_FRONTEND=true`: also start Vite frontend from `start_all.sh`.
- `START_GATEWAY=false`: skip C++ gateway from `start_all.sh`.
- `START_INIT_DB=true`: run database initialization before starting services.
- `APP_PORT`, `GATEWAY_BASE_URL`, `PYTHON_BASE_URL`: override service URLs.
- `RAG_API_ENV`, `RAG_API_VENV`, `VLLM_ENV`, `VLLM_VENV`: choose Python environments.
- `LLM_RUNTIME=api`: default remote API mode; use `LLM_RUNTIME=local_vllm` only to start local vLLM.

## Test and Validation

- `ci_smoke.sh`: Python compile, pytest, shell syntax checks, and frontend build when npm is available.
- `e2e_all.sh [file]`: full gateway-based upload, ingest, chat, message, monitor flow.
- `e2e_ingest.sh [file]`: gateway upload plus ingest polling.
- `e2e_chat.sh [file]`: internal upload/ingest plus gateway chat flow.
- `metrics_benchmark.py`: benchmark and metrics helper.

## Shared Helpers

- `env.sh`: sourced by other scripts. It provides `.env` loading, Python environment activation, Gateway auth header detection, JSON extraction, and task polling helpers.

Do not run `env.sh` directly; source it from another script.
