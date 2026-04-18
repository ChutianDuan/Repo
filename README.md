# RAG Gateway Stack

一个面向文档问答场景的分层式 RAG 项目骨架，当前由前端、C++ 网关、FastAPI 内部服务、Celery 异步任务系统组成。

这个仓库的目标不是只做一个“能跑的 demo 页面”，而是把接口层、业务层、异步计算层拆开，为后续性能优化、接入鉴权、任务调度和文档类型扩展留出清晰边界。

## 项目定位

- `frontend` 负责交互展示和调用公开 API，便于快速验证上传、索引、会话和问答流程。
- `cpp_gateway` 作为统一对外入口，负责承接浏览器请求、聚合内部服务，并为后续接入鉴权、限流、审计和高性能接口治理预留位置。
- `python_rag` 负责文档管理、切片、向量化、检索、Prompt 组织、任务管理和聊天链路，是当前迭代速度最快的业务实现层。
- `celery worker` 把 ingest/chat 等耗时任务从 API 请求线程中剥离，避免上传、向量化和生成回答时阻塞主服务。

## 为什么这样分层

### 前端

前端基于 `Vite + React + TypeScript`，定位为控制台式演示界面，直接串联健康检查、用户创建、文档上传、任务轮询、会话创建和消息回放，方便做端到端联调。

### C++ 网关

网关使用 C++ 的核心原因有两点：

- 对外接口层更适合承载高并发和高性能场景，后续可以在这里集中做连接管理、协议转换、限流和统一错误收敛。
- 鉴权、签名校验、访问控制、审计日志这类“入口能力”放在网关层更自然，后续扩展成本更低。

当前网关已承担：

- 对外暴露 `/health`、`/v1/*` 接口
- 文件上传接入
- 转发 Python 内部接口
- SSE 流式接口代理
- 浏览器跨域支持

### FastAPI 内部服务

FastAPI 负责快速开发业务逻辑，适合当前阶段高频迭代。文档上传、RAG 检索、会话消息、任务状态、内部健康检查都集中在这里实现。

选择 FastAPI 的原因很直接：

- 开发效率高，适合快速验证和演进业务
- 数据模型和接口定义清晰
- 易于和 Celery、Redis、MySQL、向量检索链路组合

### Celery Worker

Celery 用于承接 ingest 与 chat 等耗时任务，避免主 API 被切片、embedding、FAISS 构建和回答生成拖慢。

当前启动脚本默认提供可配置线程池模式：

- `CELERY_POOL=threads`
- `CELERY_CONCURRENCY=4`

这样可以把上传后的索引任务、聊天任务从请求链路中拆出去，减轻接口阻塞风险。实际部署时也可以根据机器和模型负载切换为 `prefork` 或其它池模型。

## 系统架构

```text
Browser / Frontend
        |
        v
  C++ Gateway (public API, upload, stream proxy, future auth)
        |
        +---------------------> FastAPI (internal domain APIs)
                                   |
                                   +--> MySQL
                                   +--> Redis
                                   +--> Celery Worker
                                           |
                                           +--> chunking / embedding / FAISS / chat
```

## 主要能力

- 文档上传与落盘
- 多类型文档抽取：`md/txt/json/csv/pdf/docx`
- 文档切片与向量化
- FAISS 文档级索引构建
- 会话与消息管理
- 基于检索结果的回答生成
- 引用片段 `citations` 返回
- 任务状态轮询
- SSE 流式回答代理

## 目录结构

```text
Repo/
├── cpp_gateway/          # Drogon C++ 网关
├── db/                   # MySQL 初始化与升级脚本
├── frontend/             # React + TypeScript 前端
├── python_rag/           # FastAPI + Celery + RAG 业务实现
├── scripts/              # 本地启动与 e2e 脚本
├── .env.example          # Python / Celery 环境变量示例
└── README.md
```

## 请求流转

### 文档上传与索引

1. 前端上传文件到 `cpp_gateway`
2. 网关写入 `documents` 并调用 Python 内部 ingest 接口
3. Celery worker 读取文档、切片、生成 embedding、构建 FAISS 索引
4. 任务状态写回 `tasks`，前端轮询获取进度

### 问答流程

1. 前端创建 session
2. 前端提交用户问题到网关
3. 网关创建 user message，并提交 chat 任务
4. Python 检索文档片段、组装 prompt、调用 LLM 或 mock fallback
5. assistant message 与 citations 落库
6. 前端刷新消息列表查看回答与引用

## 对外接口

网关当前对前端开放的核心接口：

- `GET /health`
- `POST /v1/users`
- `GET /v1/users/latest`
- `POST /v1/documents`
- `POST /v1/sessions`
- `POST /v1/sessions/{session_id}/messages`
- `GET /v1/sessions/{session_id}/messages`
- `GET /v1/tasks/{task_id}`
- `POST /v1/chat/stream`

Python 内部接口：

- `GET /internal/health`
- `POST /internal/documents/upload`
- `GET /internal/documents/{doc_id}`
- `POST /internal/jobs/ingest`
- `POST /internal/jobs/chat`
- `GET /internal/tasks/{task_id}`
- `POST /internal/sessions`
- `POST /internal/sessions/{session_id}/messages`
- `POST /internal/sessions/{session_id}/messages/{message_id}/status`
- `GET /internal/sessions/{session_id}/messages`
- `POST /internal/chat/stream`
- `POST /internal/search`

## 数据层

当前核心表：

- `user_account`
- `documents`
- `doc_chunks`
- `document_indexes`
- `sessions`
- `messages`
- `citations`
- `tasks`

建库与升级脚本：

- 初始化：`db/init.sql`
- 增量升级：`db/001_schema_upgrade.sql`

## 本地启动

### 1. 准备环境变量

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

根目录 `.env` 主要用于 Python API 和 Celery：

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
CELERY_POOL=threads
CELERY_CONCURRENCY=4
```

前端开发环境变量：

```bash
VITE_API_BASE_URL=
VITE_PROXY_TARGET=http://127.0.0.1:8080
```

### 2. 安装依赖

Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_rag/requirements.txt
```

Frontend:

```bash
cd frontend
npm install
```

### 3. 初始化数据库

```bash
bash scripts/init_db.sh
```

### 4. 启动 Python API

```bash
bash scripts/start_api.sh
```

### 5. 启动 Celery Worker

```bash
bash scripts/start_worker.sh
```

### 6. 启动 C++ 网关

```bash
bash cpp_gateway/scripts/start_gateway.sh
```

说明：

- 网关的数据库和 Redis 连接目前读取 `cpp_gateway/config.json`
- Python 内部服务地址通过 `PYTHON_INTERNAL_BASE_URL` 传给网关，默认是 `http://127.0.0.1:8000`
- 如果需要重新编译网关，请先确认本机已安装 Drogon 和 libcurl 开发环境

### 7. 启动前端

```bash
cd frontend
npm run dev
```

## 演示脚本

```bash
bash scripts/e2e_ingest.sh ./day7_demo.md
bash scripts/e2e_chat.sh ./day7_demo.md
```

## 当前实现特点

- 当前索引为“单文档单索引”模式，便于演示链路，后续可抽象成多文档索引或分片索引
- 当前流式回答是“先生成完整答案，再按块模拟输出”，已经具备 SSE 接口形态，但还不是真正的 provider 原生流式生成
- 当前网关已具备统一入口能力，但尚未接入认证与授权
- 当前已支持 `md/txt/json/csv/pdf/docx`，其中 PDF 仅支持可提取文本的电子文档，扫描件 OCR 仍未接入

## 后续优化方向

### 1. Ray 接入

后续计划引入 Ray，用于更精细的 GPU 资源调度和任务分配，特别适合 embedding、推理、批量文档处理等需要显卡资源编排的场景。

### 2. 网关鉴权

计划在 C++ 网关层加入：

- Token 校验
- 签名或请求认证
- 限流与访问控制
- 审计与链路追踪

### 3. 文档支持类型优化

当前文档支持已经从纯文本扩展到 PDF / DOCX，但还会继续完善：

- PDF / Office 文档解析
- 多格式统一抽取与清洗
- 更稳定的 chunk 策略
- 文档元数据与类型标签体系

### 4. 任务与资源调度优化

后续会继续完善：

- 基于任务类型的队列拆分
- 更细粒度的 worker 资源隔离
- 更清晰的任务重试与失败恢复
- 更稳定的检索缓存与索引加载策略

## 已完成的本地验证

- `python3 -m compileall python_rag`
- `npm run build`

未完成或受环境限制的部分：

- 未连接真实 MySQL / Redis 跑通整链路
- 未联调真实 LLM
- 当前机器未安装 Drogon 开发包，无法重新配置并编译 `cpp_gateway`

## 已知限制

- `cpp_gateway/build` 是带缓存的产物目录，不适合作为跨机器复用的可移植构建目录
- `cpp_gateway/config.json` 目前仍是独立配置口径，尚未与根目录 `.env` 统一
- `python_rag/modules/ingest/chunking_service.py` 还是空壳，当前切片逻辑实际位于 `python_rag/utils/text_chunker.py`
