# RAG Gateway Stack

这是一个本地 RAG / Agent 后端项目。项目把对外网关、内部业务服务、异步任务、结构化存储、向量索引、LLM 调用和前端工作台拆开，方便观察一条完整的文档入库和问答链路。

当前实现主要服务于本地开发、演示和工程验证，不把多租户隔离、生产级鉴权和部署编排作为 README 的重点。更细的接口、性能测试和排障内容放在 `docs/` 目录。

![项目运行效果](./docs/项目运行前端界面.png)

## 项目结构

系统由几类进程组成：

| 组件 | 主要职责 | 默认地址 |
| --- | --- | --- |
| React Workbench | 上传文档、创建会话、发起问答、查看引用和 Trace | `http://127.0.0.1:5173` |
| C++ Drogon Gateway | 对外 API、文件上传、CORS、健康检查聚合、SSE 代理 | `http://127.0.0.1:8080` |
| FastAPI Internal Service | 内部 API、文档处理、检索、Prompt 组装、Agent 编排、监控 | `http://127.0.0.1:8000` |
| Celery Worker | 文档解析、切片、embedding、索引构建、非流式 chat 任务 | Redis broker |
| MySQL | 用户、文档、chunk、会话、消息、引用、任务、Agent Trace | `.env` 配置 |
| Redis | Celery broker / result backend，Gateway 限流可复用 | `.env` 配置 |
| LanceDB | 本地向量索引，保存 chunk 向量和检索元数据 | `data/lancedb` |
| LLM / vLLM | OpenAI-compatible chat completion 接口 | `.env` 配置 |

架构关系：

```text
Browser / React Workbench
        |
        v
C++ Drogon Gateway
        |
        |  /v1/* 对外 API
        |  文件上传、SSE 代理、健康检查聚合
        v
FastAPI Internal Service
        |
        |-- app/modules      文档、检索、会话、消息、任务、监控
        |-- app/agent        Agent 编排、工具、记忆、Trace、流式输出
        |-- app/workers      Celery app 和 worker tasks
        |-- app/infra        MySQL、Redis、Storage 等基础设施
        |
        +--> MySQL           结构化数据 source of truth
        +--> Redis           异步任务队列和结果
        +--> Celery Worker   ingest / 非流式 chat 后台任务
        +--> LanceDB         向量召回
        +--> Embedding       sentence-transformers 或 OpenAI-compatible provider
        +--> LLM             远端 API 或本地 vLLM
```

## 核心流程

### 1. 文档入库

文档可以来自本地文件，也可以来自网页 URL。

```text
文件上传 / 网页 URL
  -> Gateway / FastAPI 保存文档记录
  -> Celery 解析正文
  -> 切分 chunk
  -> 生成 embedding
  -> 写入 LanceDB
  -> 更新 MySQL 中的文档、chunk 和索引状态
```

文件入口是 `POST /v1/documents`，支持 `.md`、`.txt`、`.json`、`.csv`、`.pdf`、`.docx`、`.xlsx`。网页入口是 `POST /v1/documents/web`，服务会抓取网页正文，保存为普通文档后进入同一条 ingest 流程。

MySQL 仍然保存文档、chunk、任务和状态；LanceDB 只负责向量召回所需的索引数据。切换 embedding 模型后，旧索引需要重新构建，避免不同向量空间混用。

### 2. 普通 RAG 问答

普通 RAG 路径适合做稳定的基线验证。

```text
用户问题
  -> 创建 user message
  -> 检索 indexed 文档
  -> LanceDB 召回 chunk_id
  -> MySQL 批量读取 chunk 正文
  -> CrossEncoder rerank
  -> 组装 Prompt
  -> 调用 LLM
  -> 保存 assistant message 和 citations
```

默认检索全局 `indexed` 文档库。如果请求显式传入 `doc_id` 或 `doc_ids`，检索范围会限制在指定文档内。

### 3. Agent 问答

Agent 路径在 RAG 基线上增加了工具循环、Trace 和会话记忆。

```text
用户问题
  -> 注入用户长期记忆、会话摘要和最近消息
  -> 判断是否需要先检索
  -> 调用只读工具
  -> 工具结果写回上下文
  -> LLM 总结或继续调用工具
  -> 保存最终回答、citations 和 Agent Trace
```

当前暴露的只读工具：

| 工具 | 用途 |
| --- | --- |
| `knowledge_search` | 检索 indexed 知识库，返回 chunk、score、标题和检索摘要。 |
| `get_document_detail` | 查询单个文档的元数据、状态和 chunk 摘要。 |
| `list_ready_documents` | 列出当前可检索文档。 |
| `list_message_citations` | 根据 assistant message 查询已保存引用。 |

工具结果统一为 `{"ok": bool, "error": string | null, "data": object}`。`ok=true` 时只使用 `data` 作为证据；工具失败时会记录失败原因，并让 LLM 基于已有观察降级回答。

为了减少模型漏检索，Agent 入口会对项目文档、代码、架构、能力、上传文档、网页导入、embedding、索引等意图做轻量路由。命中后会先执行一次 `knowledge_search`，再把结果交给 LLM 总结。问候和普通闲聊不会强制检索。

### 4. 观测与记录

系统会记录几类可回查的数据：

- `tasks`：文档 ingest、embedding、chat 等后台任务状态。
- `citations`：assistant message 对应的引用片段、chunk、score 和来源文档。
- `agent_runs` / `agent_steps` / `agent_tool_calls`：Agent 每次运行、每步决策和工具调用结果。
- `monitor`：CPU、内存、磁盘、GPU、MySQL、Redis、Worker、队列和 RAG 数据概览。

前端工作台主要用于查看这些状态，不承担核心业务逻辑。

## 代码目录

```text
Repo/
├── cpp_gateway/          # Drogon C++ 对外网关
├── python_rag/           # FastAPI、Celery、RAG、Agent 业务代码
├── frontend/             # Vite + React + TypeScript 工作台
├── db/                   # MySQL 初始化和升级脚本
├── scripts/              # 启动、E2E、smoke check 脚本
├── docs/                 # Agent、API、环境、性能和容量说明
├── data/                 # 上传文件和本地索引数据
└── tests/                # Python 单元测试和服务层测试
```

`python_rag/app` 内部边界：

```text
python_rag/app/
├── api/v1/routers/       # FastAPI 路由，保留 /internal/* 入口
├── agent/                # Agent runner、tools、memory、trace、streaming
├── modules/              # documents、ingest、retrieval、chat、sessions、messages、tasks
├── workers/              # Celery app 和 worker task
├── infra/                # MySQL、Redis、Storage、schema support
├── core/                 # config、logger、errors、exception handlers
└── shared/               # 无业务状态的公共工具函数
```

边界约定比较简单：HTTP 路由只做入口和参数转换；业务逻辑放在 `modules`；Agent 编排放在 `agent`；后台任务入口放在 `workers`；数据库、缓存、存储等基础设施放在 `infra`。

## 本地运行

### 1. 准备 `.env`

```bash
cp .env.example .env
```

常用配置包括 MySQL、Redis、存储目录、embedding、rerank 和 LLM 地址。默认模式使用远端 OpenAI-compatible LLM；只有设置 `LLM_RUNTIME=local_vllm` 时才需要启动本地 vLLM。

### 2. 安装 Python 依赖

默认只需要 `rag-api` 环境运行 FastAPI、Celery Worker 和测试。

```bash
conda create -n rag-api python=3.10
conda activate rag-api
pip install -r python_rag/requirements.txt
pip install -r python_rag/requirements-dev.txt
```

如果要使用本地 vLLM，再单独准备模型服务环境：

```bash
conda create -n vllm-qwen3 python=3.10
conda activate vllm-qwen3
pip install -r python_rag/requirements-vllm.txt
```

### 3. 初始化数据库

```bash
bash scripts/init_db.sh
```

脚本会读取根目录 `.env`，创建数据库，执行 `db/init.sql`，再按文件名顺序执行升级脚本。

### 4. 编译 Gateway

需要本机已有 C++17 编译器、CMake、Drogon、CURL、JsonCpp 以及 Drogon 的 MySQL / Redis 相关依赖。

```bash
cmake -S cpp_gateway -B cpp_gateway/build -DCMAKE_BUILD_TYPE=Debug
cmake --build cpp_gateway/build -j
```

如果使用 vcpkg，可以通过 `CMAKE_TOOLCHAIN_FILE` 或 `VCPKG_ROOT` 指定 toolchain。

### 5. 启动服务

```bash
# 可选：检查远端 LLM API；local_vllm 模式下会启动本地 vLLM
bash scripts/start_vllm.sh

# 启动 FastAPI、Worker、Gateway
bash scripts/start_all.sh

# 同时启动前端
START_FRONTEND=true bash scripts/start_all.sh
```

常用操作：

```bash
bash scripts/start_all.sh status
bash scripts/start_all.sh stop
bash scripts/start_all.sh restart
```

健康检查：

```bash
curl http://127.0.0.1:8000/internal/health
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/monitor/overview
```

## 本地模型接入

本地模型分成两类进程：LLM 由 vLLM 单独启动，提供 OpenAI-compatible `/v1/chat/completions`；embedding 和 rerank 在 `rag-api` 环境内由 FastAPI / Worker 加载，用于文档入库和检索重排。

### 本地 LLM：Qwen3-14B + vLLM

`.env` 中把 LLM 切到本地 vLLM：

```bash
LLM_RUNTIME=local_vllm
LLM_ENABLE=true
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://127.0.0.1:9000/v1
LLM_MODEL=Qwen3-14B
LLM_API_KEY=

VLLM_ENV=vllm-qwen3
VLLM_MODEL_PATH=/path/to/Qwen3-14B
VLLM_SERVED_MODEL_NAME=Qwen3-14B
VLLM_HOST=0.0.0.0
VLLM_PORT=9000
VLLM_API_KEY=
VLLM_DTYPE=auto
VLLM_GPU_MEMORY_UTILIZATION=0.9
VLLM_MAX_MODEL_LEN=
```

如果设置了 `VLLM_API_KEY`，`LLM_API_KEY` 需要使用同一个值；两者都为空时，本地 vLLM 不做 API key 校验。

GPU 按机器调整。单卡可以用：

```bash
VLLM_CUDA_VISIBLE_DEVICES=4
VLLM_TENSOR_PARALLEL_SIZE=1
```

双卡张量并行可以用：

```bash
VLLM_CUDA_VISIBLE_DEVICES=4,5
VLLM_TENSOR_PARALLEL_SIZE=2
```

启动顺序：

```bash
conda activate vllm-qwen3
bash scripts/start_vllm.sh

conda activate rag-api
bash scripts/start_all.sh
```

`scripts/start_vllm.sh` 会执行：

```bash
vllm serve "$VLLM_MODEL_PATH" \
  --host "$VLLM_HOST" \
  --port "$VLLM_PORT" \
  --served-model-name "$VLLM_SERVED_MODEL_NAME"
```

FastAPI 侧只需要通过 `LLM_BASE_URL=http://127.0.0.1:9000/v1` 调用它。

### Embedding / Rerank：Qwen 系列

当前默认检索模型也是 Qwen 系列：

```bash
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
EMBEDDING_BATCH_SIZE=32
EMBEDDING_DEVICE=auto
EMBEDDING_NORMALIZE=true
EMBEDDING_QUERY_PREFIX="Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
EMBEDDING_DOCUMENT_PREFIX=

RERANK_ENABLE=true
RERANK_PROVIDER=cross_encoder
RERANK_MODEL=Qwen/Qwen3-Reranker-0.6B
RERANK_BATCH_SIZE=16
RERANK_DEVICE=auto
RERANK_FALLBACK_TO_FAISS=true
```

这两类模型由 `rag-api` 环境加载，不经过 vLLM。没有 GPU 或显存紧张时，可以让 embedding / rerank 留在 CPU，或绑定到和 vLLM 不同的 GPU：

```bash
PYTHON_DISABLE_CUDA=true

# 或者单独绑定 API / Worker
API_CUDA_VISIBLE_DEVICES=6
WORKER_CUDA_VISIBLE_DEVICES=6
```

如果 embedding 模型发生变化，已有文档需要重新执行 ingest / embedding / index 流程。系统会记录索引用到的 embedding 模型，避免当前 query 向量和旧文档向量来自不同空间时被误用。

## 常用入口

| Method | Path | 说明 |
| --- | --- | --- |
| `POST` | `/v1/documents` | 上传文件并提交 ingest。 |
| `POST` | `/v1/documents/web` | 从网页 URL 创建文档并提交 ingest。 |
| `GET` | `/v1/documents` | 查询文档和索引状态。 |
| `POST` | `/v1/sessions` | 创建会话。 |
| `GET` | `/v1/sessions/{session_id}/messages` | 查询消息和 citations。 |
| `POST` | `/v1/chat/stream` | 普通 RAG 流式问答。 |
| `POST` | `/v1/agent/chat/stream` | Agent 流式问答，包含 step、tool call 和最终回答事件。 |
| `GET` | `/v1/tasks/{task_id}` | 查询任务状态。 |
| `GET` | `/v1/monitor/overview` | 查询系统和 RAG 监控摘要。 |

FastAPI 内部接口以 `/internal/*` 为前缀。Agent Trace 调试常用：

```text
GET /internal/agent/runs/{run_id}
GET /internal/agent/runs/{run_id}/steps
```

## 验证

Python 检查：

```bash
conda activate rag-api
python -m pytest
python -m compileall python_rag tests
```

脚本化 smoke check：

```bash
bash scripts/ci_smoke.sh
```

完整链路 E2E：

```bash
bash scripts/e2e_all.sh ./day7_demo.md
```

Agent 流式调用示例，需要先有可检索文档和会话：

```bash
curl -N -X POST http://127.0.0.1:8080/v1/agent/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id":1,"message":"根据知识库总结这个系统的架构和核心链路","trace_id":"demo-agent-001"}'
```

## 延伸文档

- [运行环境与排障手册](docs/environment.md)：Python 环境、GPU、vLLM、SSE、代理和 reranker 回退。
- [Agent MVP 说明](docs/agent_mvp.md)：Agent 演示范围、执行链路、前端和 CLI 验收。
- [Agent API 文档](docs/api_agent.md)：旧 RAG、Agent、Trace、citations 接口说明。
- [MVP 演示案例](docs/demo_cases.md)：前端和 CLI 演示步骤、预期结果和排查点。
- [RAG ingest/retrieval 容量说明](docs/rag_ingest_retrieval_capacity.md)：入库、检索和资源容量设计。
- [Embedding 微调实验](docs/embedding_finetune.md)：embedding LoRA 微调流程和实验结论。
- [性能测试指南](docs/performance_test_guide.md)：压测流程和结果留档模板。
- [Gateway 鉴权与限流](docs/gateway_auth_rate_limit.md)：Gateway API Key 和 Redis 限流配置。
- [监控指标说明](docs/monitoring_metrics.md)：系统指标、检索指标和任务指标说明。
