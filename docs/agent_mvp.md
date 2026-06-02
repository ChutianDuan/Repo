# Agent MVP 说明

本文档固化第一版 RAG Agent 的可演示范围、启动方式和验收路径。MVP 目标不是扩展工具平台，而是保证一条稳定链路可以完整展示：

```text
上传文档 -> ingest 建库 -> Agent 问答 -> knowledge_search 工具调用
-> Trace 展示 -> citations 展示
```

## MVP 范围

### 已纳入

- 文档上传、解析、切片、embedding、FAISS/BM25 索引构建。
- 旧 RAG 路径：直接检索全局 READY 文档并生成回答。
- 新 Agent 路径：LLM 先决策是否调用工具，当前只开放只读 `knowledge_search`。
- Agent Trace：记录 `agent_runs`、`agent_steps`、`agent_tool_calls`，前端流式展示执行轨迹。
- Citations：Agent 从 `knowledge_search` 结果生成 citations，并复用原有 `citations` 表和前端引用面板展示。
- 前端工作台：上传文档、查看任务、问答、Trace、引用来源和监控概览。

### 暂不纳入

- 多工具写操作、外部联网工具、代码执行工具。
- 多轮 Agent 自主规划。当前 MVP 限制为一次工具轮次后生成最终答案。
- 多租户隔离和生产级鉴权审计。网关已有 API Key/限流基础能力，但 MVP 演示默认按本地环境使用。

## 架构路径

```text
Browser / React Workbench
  |
  | /v1/documents, /v1/sessions, /v1/chat/stream, /v1/agent/chat/stream
  v
C++ Drogon Gateway
  |
  | /internal/* and /api/agent/chat/stream
  v
FastAPI Internal Service
  |
  +-- Celery Worker: ingest / old RAG async chat
  +-- AgentOrchestrator: LLM decision + knowledge_search + Trace
  +-- MySQL: docs, chunks, messages, citations, agent trace
  +-- Redis: Celery broker / backend
  +-- BM25 + FAISS: knowledge_search retrieval
```

## 启动说明

### 1. 环境变量

复制并按本机环境调整 `.env`：

```bash
cp .env.example .env
```

MVP 默认使用远端 OpenAI-compatible LLM：

```bash
LLM_RUNTIME=api
LLM_ENABLE=true
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MIMO_API_KEY=your-api-key
LLM_MODEL=glm-4.7-flash
```

如果本机没有 reranker 权重且不希望演示时下载模型，可以临时设置：

```bash
RERANK_DOWNLOAD_IF_MISSING=false
RERANK_FALLBACK_TO_FAISS=true
```

修改 `.env` 后需要重启 FastAPI 和 Worker，运行中的进程不会自动加载新配置。

### 2. 初始化数据库

```bash
bash scripts/init_db.sh
```

该脚本会执行 `db/init.sql` 和增量脚本，其中 `db/004_create_agent_tables.sql` 会创建 Agent Trace 所需的三张表。

### 3. 启动应用栈

```bash
bash scripts/start_vllm.sh
START_INIT_DB=true START_FRONTEND=true bash scripts/start_all.sh
```

默认地址：

- 前端：`http://127.0.0.1:5173`
- Gateway：`http://127.0.0.1:8080`
- FastAPI：`http://127.0.0.1:8000`

查看状态：

```bash
bash scripts/start_all.sh status
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8000/internal/health
```

停止服务：

```bash
bash scripts/start_all.sh stop
```

## 旧 RAG 与新 Agent 路径

### 旧 RAG

旧 RAG 路径由网关提交 chat 任务，Worker 执行检索和回答：

```text
POST /v1/sessions/{session_id}/messages
POST /v1/chat/stream
```

特点：

- 默认检索全局 READY 文档。
- 可选 `doc_id` / `doc_ids` 限定文档范围。
- citations 来自检索命中的 raw hits，并随 assistant message 落库。

### 新 Agent

新 Agent 演示优先使用网关流式入口：

```text
POST /v1/agent/chat/stream
```

内部调试入口：

```text
POST /internal/agent/chat
POST /internal/agent/chat/stream
GET  /internal/agent/runs/{run_id}
GET  /internal/agent/runs/{run_id}/steps
```

特点：

- Agent 先调用 LLM 判断是否需要工具。
- 当前只暴露只读 `knowledge_search`。
- 工具调用、工具结果、最终回答会写入 Trace。
- `knowledge_search` 命中的 chunk 会转换成 citations，保存到原有 `citations` 表。

## 前端验收流程

1. 打开 `http://127.0.0.1:5173`。
2. 在 `Workspace` 创建或选择用户会话。
3. 上传 `day7_demo.md` 或任意 `.md/.txt/.pdf/.docx/.xlsx/.csv/.json` 文档。
4. 等待文档状态变为 `READY`，或在 `Tasks` 页面确认 ingest 任务成功。
5. 开启流式问答与 RAG/Agent 开关。
6. 提问：`根据知识库总结这个系统的架构和核心链路`。
7. 观察右侧 `Agent Trace`：应出现决策步骤、`knowledge_search` 工具调用、工具结果和最终生成。
8. 回答完成后刷新消息或等待前端自动刷新，引用面板应显示 citations。

## CLI 验收

旧 RAG 一键链路：

```bash
bash scripts/e2e_all.sh ./day7_demo.md
```

Agent 流式链路可以在完成上传、建库、创建 session 后调用：

```bash
curl -N -X POST http://127.0.0.1:8080/v1/agent/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id":1,"message":"根据知识库总结这个系统的架构和核心链路","trace_id":"demo-agent-001"}'
```

拿到 `done.meta.run_id` 后查询持久化 Trace：

```bash
curl http://127.0.0.1:8000/internal/agent/runs/1
curl http://127.0.0.1:8000/internal/agent/runs/1/steps
```

查询消息和 citations：

```bash
curl http://127.0.0.1:8080/v1/sessions/1/messages
```

## 最小回归测试

```bash
python3 -m pytest \
  tests/test_agent_orchestrator.py \
  tests/test_agent_api.py \
  tests/test_agent_streaming_service.py \
  tests/test_knowledge_search_tool.py \
  tests/test_chat_validation.py \
  tests/test_streaming_service.py
```

更完整的本地检查：

```bash
python3 -m compileall python_rag
python3 -m pytest tests
```
