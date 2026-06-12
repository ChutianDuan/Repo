# 运行环境与排障手册

本文整理本项目本地运行时最容易混淆的部分：Python 环境拆分、GPU 分配、vLLM 配置、Gateway/前端启动、SSE 流式链路、代理影响和 reranker 离线回退。

## 1. 进程与职责

| 组件 | 默认地址 | 启动脚本 | 说明 |
| --- | --- | --- | --- |
| React Workbench | `http://127.0.0.1:5173` | `START_FRONTEND=true bash scripts/start_all.sh` 或 `cd frontend && npm run dev` | 前端调试工作台。Vite 默认代理 `/health` 和 `/v1` 到 Gateway。 |
| C++ Drogon Gateway | `http://127.0.0.1:8080` | `bash cpp_gateway/scripts/start_gateway.sh` | 对外 API、上传、CORS、健康检查聚合、SSE 代理。 |
| FastAPI Internal Service | `http://127.0.0.1:8000` | `bash scripts/start_api.sh` | 内部业务 API、检索、prompt、LLM 适配、监控。 |
| Celery Worker | Redis broker | `bash scripts/start_worker.sh` | ingest 和非流式 chat 异步任务。流式 chat 不经过 Celery。 |
| Remote LLM API | provider URL | `bash scripts/start_vllm.sh` | OpenAI-compatible API 连通性检查；默认不启动本地模型。 |
| MySQL / Redis | `.env` / `cpp_gateway/config.json` | 外部服务 | 持久化、任务队列、限流。 |

代码目录边界：FastAPI 入口仍是 `python_rag.app.main:app`；HTTP 路由位于 `python_rag/app/api/v1/routers`；业务模块位于 `python_rag/app/modules`；Agent 编排、工具、Trace 和流式输出位于 `python_rag/app/agent`；Celery app 入口为 `python_rag.app.workers.celery_app`；配置、基础设施和公共工具分别位于 `python_rag/app/core`、`python_rag/app/infra`、`python_rag/app/shared`。

重要区别：

- 前端默认使用流式回答，调用 `POST /v1/chat/stream`，不会产生 `chat_generate` Celery task。
- 非流式回答才走 `POST /v1/sessions/{session_id}/messages`，Gateway 会创建 user message 并提交 `chat_generate` Celery task。
- `GET /health` 只聚合 Gateway、Python API、MySQL、Redis 状态，不代表 vLLM 一定可用。

## 2. Python 环境拆分

默认只需要 `rag-api` 环境。只有显式配置 `LLM_RUNTIME=local_vllm` 时，才需要额外准备 `vllm-qwen3`：

| 环境 | 用途 | 主要进程 | 依赖文件 |
| --- | --- | --- | --- |
| `rag-api` | RAG 业务服务、文档解析、embedding、rerank、测试 | FastAPI、Celery Worker、pytest | `python_rag/requirements.txt`、`python_rag/requirements-dev.txt` |
| `vllm-qwen3` | 可选本地 OpenAI-compatible 大模型服务 | `vllm serve` | `python_rag/requirements-vllm.txt` |

拆分原因：vLLM 对 PyTorch、CUDA、flash-attn 等依赖更敏感；RAG API 侧还需要 `sentence-transformers`、`faiss-cpu`、文档解析和 Web 服务依赖。混在一个环境里更容易出现 torch / transformers / CUDA 版本冲突。

创建 `rag-api`：

```bash
conda create -n rag-api python=3.11
conda activate rag-api
pip install -r python_rag/requirements.txt
pip install -r python_rag/requirements-dev.txt
```

创建 `vllm-qwen3`：

```bash
conda create -n vllm-qwen3 python=3.11
conda activate vllm-qwen3
pip install -r python_rag/requirements-vllm.txt
```

如果不用 conda，也可以使用仓库内虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_rag/requirements.txt
pip install -r python_rag/requirements-dev.txt
```

## 3. `.env` 关键配置

从示例生成本地配置：

```bash
cp .env.example .env
```

基础运行环境：

```bash
RAG_API_ENV=rag-api
RAG_API_VENV=./.venv
VLLM_ENV=vllm-qwen3
VLLM_VENV=
```

LLM 默认走远端 OpenAI-compatible API：

```bash
LLM_RUNTIME=api
LLM_ENABLE=true
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MIMO_API_KEY=your-api-key
LLM_MODEL=glm-4.7-flash
```

如果需要改用其他 OpenAI-compatible 服务，只替换 `LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_MODEL`。本地 vLLM 仅在显式设置 `LLM_RUNTIME=local_vllm` 时启动，此时 `LLM_MODEL` 必须和 `VLLM_SERVED_MODEL_NAME` 保持一致。

检索与 rerank：

```bash
RETRIEVAL_RECALL_PROVIDER=lancedb
VECTOR_STORE_PROVIDER=lancedb
LANCEDB_PATH=./data/lancedb
LANCEDB_TABLE=chunk_vectors
RETRIEVAL_DENSE_TOP_K=50
RETRIEVAL_RERANK_TOP_K=5
RERANK_ENABLE=true
RERANK_PROVIDER=cross_encoder
RERANK_MODEL=BAAI/bge-reranker-base
RERANK_LOCAL_FILES_ONLY=false
RERANK_FALLBACK_TO_FAISS=true
```

如果机器无法稳定访问 HuggingFace，或 reranker 模型未完整缓存，建议临时设置：

```bash
RERANK_LOCAL_FILES_ONLY=true
RERANK_FALLBACK_TO_FAISS=true
```

这样 reranker 初始化失败会快速回退到召回顺序，不会让聊天长时间停在 `PROCESSING`。

## 4. GPU 分配建议

vLLM 独占 GPU，RAG API 的 embedding/rerank 走 CPU：

```bash
VLLM_CUDA_VISIBLE_DEVICES=0
PYTHON_DISABLE_CUDA=true
```

vLLM 与 embedding/rerank 分卡运行：

```bash
VLLM_CUDA_VISIBLE_DEVICES=4,5
VLLM_TENSOR_PARALLEL_SIZE=2
PYTHON_CUDA_VISIBLE_DEVICES=6
```

API 和 Worker 可分别覆盖：

```bash
API_CUDA_VISIBLE_DEVICES=6
WORKER_CUDA_VISIBLE_DEVICES=6
```

注意：GPU 编号会受 `CUDA_VISIBLE_DEVICES` 影响。日志里看到的 `cuda:0` 可能是进程可见范围内的第 0 张卡，不一定是物理 GPU 0。

## 5. 启动方式

默认不需要启动本地 vLLM。可以先检查远端 LLM API 连通性：

```bash
bash scripts/start_vllm.sh
```

再启动应用栈：

```bash
bash scripts/start_all.sh
```

启动前端：

```bash
START_FRONTEND=true bash scripts/start_all.sh start
```

常用操作：

```bash
bash scripts/start_all.sh status
bash scripts/start_all.sh stop
bash scripts/start_all.sh restart
```

注意：`scripts/start_all.sh restart` 会按脚本当前配置停止前端。如果没有同时设置 `START_FRONTEND=true`，重启后前端不会自动起来。需要再执行：

```bash
START_FRONTEND=true bash scripts/start_all.sh start
```

手动逐个进程启动：

```bash
bash scripts/start_api.sh
bash scripts/start_worker.sh
bash cpp_gateway/scripts/start_gateway.sh
cd frontend && npm run dev -- --host 0.0.0.0
```

## 6. 健康检查与链路验证

基础健康检查：

```bash
curl http://127.0.0.1:8000/internal/health
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/monitor/overview
```

LLM API 可用性检查：

```bash
curl -H "Authorization: Bearer ${MIMO_API_KEY:-${LLM_API_KEY}}" \
  "${LLM_BASE_URL%/}/models"
```

返回 `401 Unauthorized` 通常说明服务端口是通的，但缺少或错误配置了 API key。

流式链路最小验证：

```bash
curl -N -X POST http://127.0.0.1:8080/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"session_id":1,"content":"这份文档讲了什么？","top_k":3}'
```

正常时会不断输出：

```text
data: {"type":"delta", ...}
data: {"type":"done", ...}
```

非流式链路需要先创建会话并保证已有 READY 文档，可用：

```bash
bash scripts/e2e_all.sh ./day7_demo.md
```

## 7. 代理与本地服务

当前环境如果设置了：

```bash
HTTP_PROXY=http://127.0.0.1:17897
HTTPS_PROXY=http://127.0.0.1:17897
```

需要注意三类影响：

1. Python LLM 客户端对 `127.0.0.1`、`localhost`、私网地址会绕过代理，避免本地 vLLM 调用被代理劫持。
2. `sentence-transformers` / HuggingFace 下载会受代理影响，代理异常时 reranker 可能在初始化阶段重试。
3. C++ Gateway 的 SSE libcurl 客户端必须禁用代理访问本地 Python API。当前代码已在 `PythonSSEClient` 中设置 `CURLOPT_NOPROXY="*"` 和空 `CURLOPT_PROXY`。

如果再次出现前端卡在 `PROCESSING`，优先直接验证：

```bash
curl -N -X POST http://127.0.0.1:8080/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"session_id":1,"content":"ping","top_k":3}' \
  --max-time 30
```

如果返回 `data: {"type":"error","message":"upstream http error: 502"}`，优先检查 Gateway 到 Python API 的代理/网络问题。

## 8. 日志定位顺序

流式问答卡住时按这个顺序看：

| 日志/数据 | 看什么 |
| --- | --- |
| `logs/frontend.log` | Vite 是否启动、端口是否变成 5174 等。 |
| `logs/gateway.log` | Gateway 是否启动；Drogon 默认访问日志不一定都写这里。 |
| `logs/api.log` | 是否出现 `POST /internal/chat/stream`；如果没有，说明请求没进入 Python 流式接口。 |
| `logs/vllm.log` / `logs/vllm.manual.log` | 是否出现 `/v1/chat/completions` 请求。 |
| `logs/worker.log` | 非流式 chat 是否收到 `python_rag.tasks.chat_generate`。流式请求不看 worker。 |
| MySQL `messages` | user message 是否从 `PENDING` 变成 `PROCESSING` / `SUCCESS` / `FAILURE`，是否生成 assistant message。 |
| MySQL `tasks` | 非流式 chat / ingest 的任务状态。流式 chat 不写 task。 |

常见状态判断：

- 只有 user message `PENDING`，没有 assistant message：Gateway 只完成了创建消息，后续 stream 没进入 Python 或失败太早。
- user message `PROCESSING`，没有 vLLM 请求：问题在检索、rerank 或 prompt 组装阶段。
- vLLM 有请求但前端无输出：检查 Gateway SSE 代理、浏览器连接或 stream 解析。
- worker 没有 `chat_generate`：如果前端开启 streaming，这是正常现象。

## 9. 常见问题

### 前端显示 `Answer / PROCESSING / 正在生成`，但 vLLM 没请求

先确认前端是否启用了 streaming。启用时不会创建 Celery chat task。

然后检查数据库最近消息：如果只有 user message 处于 `PENDING`，通常是 Gateway 创建消息后没有成功进入 Python `/internal/chat/stream`。常见原因是 SSE 上游请求被代理影响或 Gateway 未加载最新二进制。

修复后需要重新编译并重启 Gateway：

```bash
cmake --build cpp_gateway/build -j 4
bash scripts/start_all.sh restart
START_FRONTEND=true bash scripts/start_all.sh start
```

### vLLM 已启动，但前端 health 不是 ok

`/health` 不检查 vLLM，只检查 Gateway、Python API、MySQL、Redis。vLLM 是否可用请用 `/v1/models` 或实际 chat completion 验证。

### reranker 报 HuggingFace SSL / proxy / cache 错误

`CrossEncoder` 初始化会尝试访问或校验 HuggingFace 模型文件。网络代理异常或缓存不完整时，可临时设置：

```bash
RERANK_LOCAL_FILES_ONLY=true
RERANK_FALLBACK_TO_FAISS=true
```

如果需要真正启用 rerank，需要把 `RERANK_MODEL` 对应模型完整下载到本地缓存，或改成完整本地模型路径。

### 前端端口不是 5173

如果 5173 已被占用，Vite 会自动切到 5174。`logs/frontend.log` 会显示实际地址。需要固定端口时先停止旧 Vite 进程，再重新启动。

### 重启后仍像旧配置

检查是否有残留进程：

```bash
ps -ef | rg 'uvicorn|celery|cpp_gateway|vite|vllm'
```

如果旧 worker 仍在，它可能继续消费 Redis 队列。清理旧进程后重新启动应用栈。
