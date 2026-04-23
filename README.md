# RAG Gateway Stack

面向文档知识库问答的分层式 RAG 后端系统。项目重点不是单页前端 demo，而是把外部 API 入口、内部业务服务、异步任务、数据库、向量索引、LLM 调用和监控链路拆开，形成一套可扩展的工程骨架。

当前系统由 `C++ Drogon Gateway`、`FastAPI Internal Service`、`Celery Worker`、`MySQL`、`Redis`、`FAISS`、`Embedding Model`、`OpenAI-compatible LLM / vLLM` 和 `React Workbench` 组成。前端主要作为调试和演示工作台，后端链路是项目核心。

## 项目亮点

- `C++ Gateway` 作为统一外部入口，负责 `/v1/*` API、文件上传、CORS、健康检查聚合和 SSE 流式回答代理。
- `FastAPI` 承载内部业务 API，将文档、任务、会话、消息、检索、LLM 和监控模块拆分。
- `Celery + Redis` 处理文档解析、切片、embedding、FAISS 索引构建和异步问答任务，避免长耗时流程阻塞请求。
- `MySQL` 持久化用户、文档、chunk、索引元数据、任务状态、会话、消息和 citations。
- `FAISS` 保存每个文档的向量索引，并通过 `document_indexes.embedding_model` 防止模型切换后混用旧索引。
- 问答结果保存引用来源，支持回答可追溯和前端引用面板展示。
- 提供服务监控接口，聚合 CPU、内存、磁盘、GPU、MySQL、Redis、Worker、任务队列和 RAG 数据概览。

## 架构概览

```text
Browser / React Workbench
        |
        v
C++ Drogon Gateway
        |-- public API
        |-- upload validation
        |-- CORS
        |-- health aggregation
        |-- SSE proxy
        |-- auth / rate limit ready
        |
        v
FastAPI Internal Service
        |-- document / task / session / message APIs
        |-- retrieval and prompt orchestration
        |-- LLM and monitor adapters
        |
        +--> MySQL        : users, documents, chunks, indexes, sessions, messages, citations, tasks
        +--> Redis        : Celery broker / result backend
        +--> Celery       : ingest and chat async jobs
        +--> FAISS        : per-document vector index
        +--> Embedding    : sentence-transformers or OpenAI-compatible provider
        +--> LLM / vLLM   : OpenAI-compatible chat completion endpoint
```

## 目录结构

```text
Repo/
├── cpp_gateway/          # Drogon C++ 对外网关
├── python_rag/           # FastAPI + Celery + RAG 业务实现
├── db/                   # MySQL 初始化脚本与增量升级脚本
├── frontend/             # Vite + React + TypeScript 前端工作台
├── scripts/              # 数据库、API、worker、vLLM、E2E 启动脚本
├── docs/                 # 实验和设计说明
├── data/                 # 上传文件与索引数据目录
├── .env.example          # 后端环境变量示例
└── README.md
```

## 后端组件

| 组件 | 责任 |
| --- | --- |
| `cpp_gateway` | 对外暴露 `/health` 和 `/v1/*`，处理文件上传、CORS、SSE 代理和内部服务转发，后续适合放鉴权、限流、审计。 |
| `python_rag` | 内部业务服务，负责用户、文档、任务、会话、检索、Prompt、LLM 调用和监控概览。 |
| `celery worker` | 执行耗时任务，包括文档 ingest、embedding、FAISS 构建和异步 chat。 |
| `MySQL` | 持久化业务数据、任务状态、引用来源和索引元数据。 |
| `Redis` | Celery broker / result backend，也参与服务健康检查。 |
| `FAISS` | 保存向量索引，当前以单文档索引为主。 |

## 核心链路

### 文档 Ingest

1. 前端或 API 客户端上传文档到 `/v1/documents`。
2. C++ Gateway 校验文件类型、计算 SHA-256、落盘，并写入 `documents`。
3. Gateway 调用 FastAPI `/internal/jobs/ingest` 提交异步任务。
4. Celery Worker 抽取文本、切片、生成 embedding、构建 FAISS 索引。
5. Worker 写入 `doc_chunks`、`document_indexes`，并更新 `tasks` 和 `documents.status`。
6. 客户端通过 `/v1/tasks/{task_id}` 轮询任务进度。

### RAG 问答

1. 客户端创建 session。
2. 客户端提交问题到 `/v1/sessions/{session_id}/messages`。
3. Gateway 先创建 user message，再提交 chat task。
4. Celery Worker 基于 FAISS 做 Top-K 检索，组装 context 和 prompt。
5. 调用 OpenAI-compatible LLM；失败时可按配置启用 mock fallback。
6. assistant message 和 citations 落库。
7. 客户端刷新消息列表并展示引用来源。

## 设计决策

| 决策 | 原因 |
| --- | --- |
| 使用 C++ Gateway 作为外部入口 | 将浏览器可访问 API 与内部业务服务隔离，后续可以集中承载鉴权、限流、审计、SSE 代理和上传控制。 |
| 使用 Celery 处理 ingest/chat | 文档解析、embedding、索引构建和 LLM 调用都是长耗时任务，异步化可以避免 API 请求长时间阻塞。 |
| MySQL 与 FAISS 分离 | MySQL 维护业务状态和引用关系，FAISS 专注向量检索，二者职责清晰。 |
| 保存 citations | 每次回答都可以追溯到具体 `doc_id`、`chunk_id`、`chunk_index` 和 score，方便用户校验答案来源。 |
| 保存 embedding 模型信息 | `document_indexes.embedding_model` 用于检测索引与当前 embedding 模型是否一致，避免模型切换后继续查询旧向量空间。 |
| Gateway 透传内部接口状态 | 外部错误响应能够保留上游状态，便于前端和调试脚本判断失败原因。 |

## 数据模型

| 表 | 用途 |
| --- | --- |
| `user_account` | 用户基础信息。 |
| `documents` | 上传文档元数据、落盘路径、哈希、处理状态和错误信息。 |
| `doc_chunks` | 文档切片内容、chunk 顺序和 token 估算。 |
| `document_indexes` | FAISS 索引路径、mapping 路径、embedding 模型、向量维度和 chunk 数。 |
| `tasks` | Celery 任务状态、进度、错误和阶段 meta。 |
| `sessions` | 问答会话。 |
| `messages` | 用户/助手消息、状态和 meta_json。 |
| `citations` | 回答引用的 chunk、分数和片段。 |

## Embedding 与微调实验

系统的 embedding 层支持 `sentence_transformers` 和 OpenAI-compatible provider，并提供 batch size、device、normalize、query/document prefix 等配置。索引构建时会把 embedding 模型名写入 `document_indexes`，查询时校验当前模型，模型切换后需要重新 ingest。

项目额外整理了 KALM embedding 的 LoRA triplet 微调实验。整体思路是先下载公开数据集，用 BM25 构造弱监督正负样本并完成第一轮训练；随后用训练后的 embedding 模型重新检索和挖掘数据对，构建更贴近模型分布的 triplet 样本，再进行第二轮训练，从而实现自举式提升。实验使用 1727 条 triplet 样本评估，主要观察正负样本 margin 和伪检索排序指标。完整说明见 [docs/embedding_finetune.md](docs/embedding_finetune.md)。

部署后的性能验证、压测流程和留档模板见 [docs/performance_test_guide.md](docs/performance_test_guide.md)。

微调流程：

```text
Public Dataset
      |
      v
BM25 weak supervision
      |-- query-positive pairs
      |-- hard negatives
      v
LoRA training round 1
      |
      v
Embedding model mining
      |-- re-retrieve candidates
      |-- rebuild triplets
      v
LoRA training round 2
      |
      v
Evaluate triplet margin and pseudo retrieval metrics
```

Triplet 级别指标：

| 指标 | Base | LoRA | LoRA - Base |
| --- | ---: | ---: | ---: |
| Triplet Accuracy | 0.759699 | 0.910828 | +0.151129 |
| Mean Margin | 0.113591 | 0.245272 | +0.131681 |
| Mean Positive Score | 0.756601 | 0.525304 | -0.231297 |
| Mean Negative Score | 0.643010 | 0.280032 | -0.362978 |

伪检索指标：

| 指标 | Base | LoRA | LoRA - Base |
| --- | ---: | ---: | ---: |
| Recall@1 | 0.729589 | 0.822235 | +0.092646 |
| MRR@5 | 0.843872 | 0.873982 | +0.030110 |
| NDCG@5 | 0.877075 | 0.891069 | +0.013994 |
| MRR@10 | 0.845246 | 0.876023 | +0.030777 |
| NDCG@10 | 0.880315 | 0.896082 | +0.015767 |
| Recall@5 | 0.972206 | 0.940938 | -0.031268 |
| Recall@10 | 0.982050 | 0.956572 | -0.025478 |

结论：LoRA 后 `Triplet Accuracy` 和 `Mean Margin` 明显提升，伪检索的 Top-1 命中和整体排序质量提升；但 `Recall@5` 和 `Recall@10` 有小幅下降，说明模型更偏向把最相关片段提前，而宽召回能力需要继续结合真实业务问答集评估。

## 后端公开接口

前端和外部客户端优先通过 C++ Gateway 访问：

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 网关聚合健康检查。 |
| `POST` | `/v1/users` | 创建用户。 |
| `GET` | `/v1/users/latest` | 最近用户列表。 |
| `POST` | `/v1/documents` | 上传文档并提交 ingest 任务。 |
| `GET` | `/v1/documents/{doc_id}` | 查询文档详情。 |
| `POST` | `/v1/sessions` | 创建会话。 |
| `POST` | `/v1/sessions/{session_id}/messages` | 创建用户消息并提交 chat 任务。 |
| `GET` | `/v1/sessions/{session_id}/messages` | 获取消息和 citations。 |
| `GET` | `/v1/tasks` | 查询任务列表。 |
| `GET` | `/v1/tasks/{task_id}` | 查询单个任务状态。 |
| `POST` | `/v1/chat/stream` | SSE 流式回答代理。 |
| `GET` | `/v1/monitor/overview` | CPU / GPU / MySQL / Redis / Worker / 队列 / RAG 摘要。 |

FastAPI 内部接口以 `/internal/*` 为前缀，不建议浏览器直接访问。

## 本地运行

### 1. 初始化环境变量

```bash
cp .env.example .env
```

最小必填配置通常是：

```bash
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=ai_app
MYSQL_USER=ai_user
MYSQL_PASSWORD=ai_password

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2

APP_HOST=0.0.0.0
APP_PORT=8000

STORAGE_ROOT=./data
UPLOAD_DIR=./data/uploads
INGEST_CHUNK_SIZE=800
INGEST_CHUNK_OVERLAP=100

EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DEVICE=auto

LLM_ENABLE=true
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://127.0.0.1:9000/v1
LLM_MODEL=local-llm
CHAT_ENABLE_MOCK_FALLBACK=true
```

注意：`cpp_gateway/config.json` 目前仍独立配置 MySQL / Redis / 监听端口。根目录 `.env` 会被 `cpp_gateway/scripts/start_gateway.sh` 读取，但 Drogon 的数据库连接仍以 `cpp_gateway/config.json` 为准。

### 2. 安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_rag/requirements.txt
```

监控接口会使用 `psutil` 读取 CPU、内存、磁盘。GPU 指标优先通过 `nvidia-smi` 读取；没有 NVIDIA 驱动时返回空 GPU 列表，不影响主流程。

### 3. 初始化数据库

```bash
bash scripts/init_db.sh
```

脚本会读取根目录 `.env`，创建 `MYSQL_DATABASE`，执行 `db/init.sql`，再按文件名字典序执行 `db/*_schema_upgrade.sql`。

如果业务用户不存在，或没有建库权限，可以在 `.env` 中补充：

```bash
MYSQL_ADMIN_USER=root
MYSQL_ADMIN_PASSWORD=your_root_password
```

### 4. 编译 C++ Gateway

依赖：

- `cmake`
- C++17 编译器
- Drogon
- CURL
- JsonCpp
- MySQL / Redis 相关 Drogon 依赖

```bash
cmake -S cpp_gateway \
      -B cpp_gateway/build \
      -DCMAKE_BUILD_TYPE=Debug

cmake --build cpp_gateway/build -j
```

如果使用 vcpkg：

```bash
-DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake
```

### 5. 启动服务

建议每个服务单独开一个终端：

```bash
# 1. MySQL / Redis 先启动，并初始化数据库
bash scripts/init_db.sh

# 2. 可选：启动 vLLM
source .venv/bin/activate
bash scripts/start_vllm.sh

# 3. 启动 FastAPI
source .venv/bin/activate
bash scripts/start_api.sh

# 4. 启动 Celery Worker
source .venv/bin/activate
bash scripts/start_worker.sh

# 5. 启动 C++ Gateway
bash cpp_gateway/scripts/start_gateway.sh
```

健康检查：

```bash
curl http://127.0.0.1:8000/internal/health
curl http://127.0.0.1:8000/internal/monitor/overview
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/monitor/overview
```

## E2E 验证

先创建用户：

```bash
curl -X POST http://127.0.0.1:8080/v1/users \
  -H "Content-Type: application/json" \
  -d '{"name":"demo-user"}'
```

上传与索引：

```bash
bash scripts/e2e_ingest.sh ./day7_demo.md
```

完整问答：

```bash
bash scripts/e2e_chat.sh ./day7_demo.md
```

如果切换 embedding 模型，历史文档需要重新 ingest，否则 FAISS 索引维度或向量空间可能不一致。

## 前端工作台

前端是 `Vite + React + TypeScript` 的 RAG 工作台，服务于演示和调试。

| 页面 | 说明 |
| --- | --- |
| `Workspace` | 核心问答工作区，包含会话、消息、上传、RAG 开关、引用面板。 |
| `Documents` | 文档上传、索引状态、chunk/向量化摘要、文档详情。 |
| `Tasks` | ingest/chat 任务表、进度、meta_json、错误日志。 |
| `Monitor` | CPU / GPU / 内存 / MySQL / Redis / Worker / 队列 / RAG 摘要。 |
| `Settings` | 网关地址、用户、top_k、chunk 参数和模型显示名。 |

启动：

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

本地开发时建议让 `VITE_API_BASE_URL` 为空，让 Vite 把 `/health` 和 `/v1` 代理到 Gateway：

```bash
VITE_API_BASE_URL=
VITE_PROXY_TARGET=http://127.0.0.1:8080
```

构建：

```bash
cd frontend
npm run build
```

## 当前限制

- Gateway 的 MySQL / Redis 连接还没有完全收敛到根目录 `.env`，目前仍依赖 `cpp_gateway/config.json`。
- `Monitor` 的历史趋势目前是前端近端采样，尚未落库保存时序指标。
- GPU 监控依赖 `nvidia-smi`，非 NVIDIA 环境会返回空数组。
- 当前索引是单文档单 FAISS 索引，后续可扩展为多文档知识库、分片索引或向量数据库。
- SSE 流式接口形态完整，但生成侧仍以先得到完整答案再分块输出为主，后续可升级为真实 token streaming。
- PDF 仅支持可提取文本的电子文档，扫描件 OCR 尚未接入。
- 尚未接入鉴权、租户隔离、请求限流和审计日志。

## 后续升级方向

- Docker Compose 一键启动 MySQL、Redis、FastAPI、Celery Worker 和 C++ Gateway。
- 完善自动化测试，覆盖文档上传、ingest、chat、citations 和任务状态。
- Gateway 增加 API Key 鉴权、Redis 限流、request id 透传和统一错误响应。
- LLM 调用升级为真实 token streaming，并记录首 token 延迟和总耗时。
- 从单文档索引扩展到知识库级多文档检索。
- 将 embedding LoRA 接入方式标准化，支持合并模型路径或 adapter 加载。

## 推荐验证命令

```bash
python3 -m compileall python_rag
cd frontend && npm run build
bash -n scripts/init_db.sh scripts/start_api.sh scripts/start_worker.sh scripts/start_vllm.sh cpp_gateway/scripts/start_gateway.sh
```

当前机器如果没有 Drogon 开发包，需要先安装 Drogon 或设置 `Drogon_DIR` / `CMAKE_PREFIX_PATH` 后再编译 `cpp_gateway`。
