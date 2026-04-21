# RAG Gateway Stack

一个面向文档检索与问答的分层式 RAG 工程。当前由 `React 前端`、`C++ Gateway`、`FastAPI 内部服务`、`Celery Worker`、`MySQL`、`Redis` 和 `FAISS` 组成。

项目重点不是单页 demo，而是把外部入口、业务服务、异步任务、数据库和检索链路拆开，方便后续扩展鉴权、限流、任务调度、监控和多文档知识库。

## 架构概览

```text
Browser / Frontend
        |
        v
C++ Gateway  : public API, upload, CORS, stream proxy, future auth/rate limit
        |
        v
FastAPI      : internal business APIs, RAG orchestration
        |
        +--> MySQL       : users, documents, chunks, sessions, messages, citations, tasks
        +--> Redis       : Celery broker/result backend, lightweight health cache
        +--> Celery      : ingest/chat async jobs
        +--> FAISS       : per-document vector index
        +--> LLM/vLLM    : OpenAI-compatible generation endpoint
```

## 目录结构

```text
Repo/
├── cpp_gateway/          # Drogon C++ 对外网关
├── db/                   # MySQL 初始化脚本与增量升级脚本
├── frontend/             # Vite + React + TypeScript 前端工作台
├── python_rag/           # FastAPI + Celery + RAG 业务实现
├── scripts/              # 数据库、API、worker、vLLM、E2E 启动脚本
├── data/                 # 上传文件与索引数据目录
├── .env.example          # 后端环境变量示例
└── README.md
```

## 后端重点

### 后端组件分工

| 组件 | 责任 |
| --- | --- |
| `cpp_gateway` | 对外暴露 `/health` 和 `/v1/*`，处理文件上传、CORS、SSE 代理，后续适合放鉴权、限流、审计。 |
| `python_rag` | 内部业务服务，负责用户、文档、任务、会话、检索、Prompt、LLM 调用和监控概览。 |
| `celery worker` | 执行耗时任务，包括文档 ingest、embedding、FAISS 构建和异步 chat。 |
| `MySQL` | 持久化业务数据和任务状态。 |
| `Redis` | Celery broker/result backend，同时用于健康检查轻量写入。 |

### 数据库初始化

推荐统一使用脚本：

```bash
bash scripts/init_db.sh
```

脚本行为：

- 读取根目录 `.env`
- 使用 `MYSQL_DATABASE` 创建数据库
- 执行 `db/init.sql`
- 按文件名字典序执行 `db/*_schema_upgrade.sql`
- 最后输出当前数据库表列表

如果 `MYSQL_USER` 还不存在，或业务用户没有建库权限，请在 `.env` 中加 admin 账号：

```bash
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=ai_app
MYSQL_USER=ai_user
MYSQL_PASSWORD=ai_password

MYSQL_ADMIN_USER=root
MYSQL_ADMIN_PASSWORD=your_root_password
```

如果已经手工创建了业务用户，并且该用户有目标库权限，可以不配置 `MYSQL_ADMIN_USER`。

核心表：

| 表 | 用途 |
| --- | --- |
| `user_account` | 用户基础信息。 |
| `documents` | 上传文档元数据、落盘路径、处理状态。 |
| `doc_chunks` | 文档切片内容和 chunk 顺序。 |
| `document_indexes` | FAISS 索引路径、embedding 模型、维度和 chunk 数。 |
| `sessions` | 问答会话。 |
| `messages` | 用户/助手消息和 meta_json。 |
| `citations` | 回答引用的 chunk、分数和片段。 |
| `tasks` | Celery 任务状态、进度、错误和阶段 meta。 |

### 后端环境变量

复制示例文件：

```bash
cp .env.example .env
```

最小必填项通常是：

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

### Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_rag/requirements.txt
```

监控接口会使用 `psutil` 读取 CPU、内存、磁盘。GPU 指标优先通过系统命令 `nvidia-smi` 读取；没有 NVIDIA 驱动时会返回空 GPU 列表，不影响主流程。

### C++ Gateway 编译

依赖：

- `cmake`
- C++17 编译器
- Drogon
- CURL
- JsonCpp
- MySQL / Redis 相关 Drogon 依赖

示例：

```bash
cmake -S cpp_gateway \
      -B cpp_gateway/build \
      -DCMAKE_BUILD_TYPE=Debug

cmake --build cpp_gateway/build -j
```

如果使用 vcpkg，请按你的环境补充：

```bash
-DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake
```

### 启动顺序

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

### 后端公开接口

前端应优先通过 C++ Gateway 访问这些接口：

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

### 核心链路

文档 ingest：

1. 前端上传文档到 `/v1/documents`
2. C++ Gateway 校验类型、落盘、写入 `documents`
3. Gateway 调用 FastAPI `/internal/jobs/ingest`
4. Celery worker 抽取文本、切片、embedding、构建 FAISS
5. 写入 `doc_chunks`、`document_indexes`，更新 `tasks` 和 `documents.status`
6. 前端轮询 `/v1/tasks/{task_id}` 获取进度

问答：

1. 前端创建 session
2. 前端提交问题到 `/v1/sessions/{session_id}/messages`
3. Gateway 先创建 user message，再提交 chat task
4. Celery 检索 FAISS，组装 context 和 prompt
5. 调用 LLM；失败时可按配置使用 mock fallback
6. assistant message 和 citations 落库
7. 前端刷新消息并展示引用来源

### E2E 验证

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

如果切换了 embedding 模型，历史文档需要重新 ingest，否则 FAISS 索引维度或向量空间可能不一致。

## 前端

前端是 `Vite + React + TypeScript` 的 RAG 工作台，页面按功能拆分：

| 页面 | 说明 |
| --- | --- |
| `Workspace` | 核心问答工作区，包含会话、消息、上传、RAG 开关、引用面板。 |
| `Documents` | 文档上传、索引状态、chunk/向量化摘要、文档详情。 |
| `Tasks` | ingest/chat 任务表、进度、meta_json、错误日志。 |
| `Monitor` | CPU / GPU / 内存 / MySQL / Redis / Worker / 队列 / RAG 摘要。 |
| `Settings` | 网关地址、用户、top_k、chunk 参数和模型显示名。 |

安装与启动：

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

前端环境变量：

```bash
VITE_API_BASE_URL=
VITE_PROXY_TARGET=http://127.0.0.1:8080
```

本地开发时建议让 `VITE_API_BASE_URL` 为空，这样 Vite 会把 `/health` 和 `/v1` 代理到 Gateway。

构建：

```bash
cd frontend
npm run build
```

## 当前已知限制

- Gateway 的 MySQL / Redis 连接还没有完全收敛到根目录 `.env`，目前仍依赖 `cpp_gateway/config.json`。
- `Monitor` 的历史趋势还只是前端近端采样，尚未落库保存时序指标。
- GPU 监控依赖 `nvidia-smi`，非 NVIDIA 环境会返回空数组。
- 当前索引是单文档单 FAISS 索引，后续可扩展为多文档知识库、分片索引或向量数据库。
- SSE 流式接口当前是接口形态完整，但生成侧仍以先得到完整答案再分块输出为主。
- PDF 仅支持可提取文本的电子文档，扫描件 OCR 尚未接入。
- 尚未接入鉴权、租户隔离、请求限流和审计日志。

## 推荐验证命令

```bash
python3 -m compileall python_rag
cd frontend && npm run build
bash -n scripts/init_db.sh scripts/start_api.sh scripts/start_worker.sh scripts/start_vllm.sh cpp_gateway/scripts/start_gateway.sh
```

当前机器如果没有 Drogon 开发包，需要先安装 Drogon 或设置 `Drogon_DIR` / `CMAKE_PREFIX_PATH` 后再编译 `cpp_gateway`。
