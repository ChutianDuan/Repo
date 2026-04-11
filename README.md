# RAG Demo Repo

这是一个三层结构的 RAG 演示仓库：

- `python_rag/`：内部 Python 服务，负责文档上传、切片、向量检索、任务状态、会话消息和 LLM 调用。
- `cpp_gateway/`：C++ 网关，对外暴露 `/v1/*` 接口，并代理 Python 内部服务。
- `frontend/`：最小可演示前端，基于 Vite + React + TypeScript，直接调用网关完成上传、索引、会话、提问和消息回放。

## 当前整理结果

这次整理主要做了四类事情：

- 修正 Python 内部 API 中残留的旧模块导入、错误的返回结构、错误码和消息持久化问题。
- 对齐 MySQL 表结构与代码使用方式，补上 `messages.meta_json`、citations 关联、用户字段映射等关键口径。
- 补全一个可直接演示流程的前端页面，而不是仅保留类型文件。
- 补全依赖、脚本、环境样例和文档，方便按步骤启动。

## 目录结构

```text
Repo/
├── cpp_gateway/          # Drogon C++ 网关
├── db/                   # MySQL 初始化和升级脚本
├── frontend/             # Vite + React + TypeScript 演示前端
├── python_rag/           # FastAPI + Celery + MySQL + Redis + RAG 逻辑
├── scripts/              # 初始化、启动、e2e 脚本
├── .env.example          # 后端环境变量示例
└── README.md
```

## 架构说明

### 1. Public API

对前端开放的主要接口由 `cpp_gateway` 提供：

- `GET /health`
- `POST /v1/documents`
- `POST /v1/sessions`
- `POST /v1/sessions/{session_id}/messages`
- `GET /v1/sessions/{session_id}/messages`
- `GET /v1/tasks/{task_id}`

### 2. Internal API

Python 内部接口主要给网关和任务系统使用：

- `GET /internal/health`
- `POST /internal/documents/upload`
- `GET /internal/documents/{doc_id}`
- `POST /internal/jobs/ingest`
- `POST /internal/jobs/chat`
- `GET /internal/tasks/{task_id}`
- `POST /internal/sessions`
- `POST /internal/sessions/{session_id}/messages`
- `GET /internal/sessions/{session_id}/messages`
- `POST /internal/chat/stream`
- `POST /internal/search`

### 3. 数据流

1. 前端把文件发给 C++ 网关。
2. 网关落库 `documents`，再向 Python 提交 ingest 任务。
3. Python 读取文件、切片、生成 embedding、构建 FAISS 索引，并更新 `document_indexes`。
4. 用户创建会话并提交问题。
5. 网关先创建 user message，再向 Python 提交 chat 任务。
6. Python 检索 chunks、构造 prompt、调用 LLM 或 mock fallback、保存 assistant message 和 citations。
7. 前端通过轮询任务状态和拉取消息列表完成演示。

## MySQL 表

核心表如下：

- `user_account`
- `documents`
- `doc_chunks`
- `document_indexes`
- `sessions`
- `messages`
- `citations`
- `tasks`

其中这次重点核对了几件事：

- `messages` 需要 `meta_json JSON` 字段，代码已经按此口径写入和读取。
- `documents.user_id`、`doc_chunks.doc_id`、`citations.doc_id/chunk_id/message_id` 都需要明确外键。
- `user_account` 的数据库列名是 `username`，接口层统一映射成 `name` 返回。
- 前端类型已经按真实响应结构更新，不再把上传接口误当成仅返回 `doc_id + status`。

初始化脚本：

- 首次建库：`db/init.sql`
- 增量兼容升级：`db/001_schema_upgrade.sql`

## AI 审核结论

这次没有做真实模型联调，但完成了逻辑审计和关键修正：

- 修正了聊天链路里 assistant message 与 citations 的落库签名不一致问题。
- 修正了 `messages` 仓储层对 `meta_json` 的支持，避免运行时只能写 message 不能写元数据。
- 修正了 `update_message_status` 的 SQL 语法错误。
- 修正了检索上下文组装时固定用全局 `CHAT_TOP_K` 截断的问题，改为优先尊重本次请求的 `top_k`。
- 修正了 `embedding_service` 中 GPU 选择逻辑始终落到 `cpu` 的错误。
- 保留 LLM 失败时的 `mock fallback`，保证在本地未配置模型时仍可验证链路。
- `stream_chat` 仍是“先生成整段答案，再按块模拟 SSE 输出”的实现，不是真正的 provider 原生流式输出。

## 环境变量

后端可从根目录 `.env` 读取配置，推荐先复制：

```bash
cp .env.example .env
```

关键变量：

- `MYSQL_HOST MYSQL_PORT MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD`
- `REDIS_HOST REDIS_PORT REDIS_DB REDIS_PASSWORD`
- `CELERY_BROKER_URL CELERY_RESULT_BACKEND`
- `APP_HOST APP_PORT`
- `LLM_ENABLE LLM_PROVIDER LLM_BASE_URL LLM_API_KEY LLM_MODEL`
- `CHAT_TOP_K CHAT_MIN_RETRIEVAL_SCORE CHAT_MAX_CHUNK_CHARS`

前端环境变量在 `frontend/.env.example`：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8080
```

## 启动方式

### 1. 安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_rag/requirements.txt
```

### 2. 初始化 MySQL

```bash
bash scripts/init_db.sh
```

### 3. 启动 Python API

```bash
bash scripts/start_api.sh
```

### 4. 启动 Celery Worker

```bash
bash scripts/start_worker.sh
```

### 5. 启动 C++ 网关

仓库里已有 `cpp_gateway/build/`，但本次没有重新编译。若本地具备 Drogon / CMake 环境，可自行重新 build 后运行。

### 6. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## 演示方式

### 前端演示

打开前端页面后按顺序操作：

1. 检查健康状态
2. 上传文档并等待 ingest 完成
3. 创建 session
4. 提问并等待 chat 任务完成
5. 刷新消息并查看 citations

### 脚本演示

```bash
bash scripts/e2e_ingest.sh ./day7_demo.md
bash scripts/e2e_chat.sh ./day7_demo.md
```

## 本地验证结果

这次在当前机器上完成了以下验证：

- `python3 -m compileall python_rag` 通过
- `npm install` 完成
- `npm run typecheck` 通过
- `npm run build` 通过

没有完成的验证：

- 未实际连接本地 MySQL / Redis / Celery 跑通真实任务
- 未真实调用外部 LLM
- 未重新编译 `cpp_gateway`

## 已知限制

- 仓库当前 worktree 里 `docker-compose.yml` 处于删除状态，本次没有擅自恢复。
- 根目录现有 `.env` 可能包含本地真实配置，建议只把 `.env.example` 作为共享模板。
- `cpp_gateway` 上传路径已经统一到 `./data/uploads`，但这次没有在本机重新编译验证。
- `python_rag/modules/ingest/chunking_service.py` 目前仍为空，实际切片逻辑来自 `python_rag/utils/text_chunker.py`。
