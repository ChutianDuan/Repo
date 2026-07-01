# MVP 演示案例

本文档给出演示脚本和预期观察点。建议先跑“完整主线演示”，再按需要展示旧 RAG 对照、无证据回答和 Trace 查询。

## 前置条件

服务已启动：

```bash
bash scripts/start_all.sh status
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8000/internal/health
```

准备演示文档：

```bash
ls ./day7_demo.md
```

如果文档不存在，可以换成任意小型 `.md` 或 `.txt` 文件。

## 案例 1：完整主线演示

目标：完成验收标准中的完整链路。

### 操作

1. 打开前端：`http://127.0.0.1:5173`。
2. 在 `Workspace` 创建会话。
3. 上传 `day7_demo.md`，或在网页导入输入框提交一个可直接访问的 `http(s)` URL。
4. 在 `Tasks` 或文档列表等待 ingest 成功，文档状态为 `READY`。
5. 保持流式问答开启，并使用 Agent/RAG 开关进入 Agent 路径。
6. 提问：

```text
根据知识库总结这个系统的架构、核心链路和 Agent MVP 能力。
```

### 预期

- 上传后出现 ingest 任务，最终 `SUCCESS`。
- Agent Trace 面板出现执行步骤。项目文档类问题通常会先出现一次 `forced_tool_call`。
- Trace 中出现 `knowledge_search` 的 `tool_call` 和 `tool_result`，工具结果为 `ok/error/data` 结构。
- 回答内容基于上传文档。
- 回答完成后消息刷新，引用面板展示至少 1 条 citation，包含 `doc_id`、`chunk_index`、score 和 snippet。

## 案例 2：旧 RAG 对照

目标：确认旧 RAG 路径仍可运行。

```bash
bash scripts/e2e_all.sh ./day7_demo.md
```

预期：

- 创建用户成功。
- 上传文档成功。
- ingest 任务成功。
- 创建 session 成功。
- `/v1/sessions/{session_id}/messages` 提交旧 RAG chat 任务成功。
- chat 任务成功。
- 最终消息中 assistant message 带 citations。

## 案例 3：Agent 流式 API 演示

目标：不依赖前端，直接展示 Agent SSE 事件。

先准备 `SESSION_ID`。如果已经通过前端创建过会话，可直接使用对应 ID；也可以用接口创建：

```bash
curl -X POST http://127.0.0.1:8080/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"title":"Agent CLI Demo"}'
```

调用 Agent：

```bash
curl -N -X POST http://127.0.0.1:8080/v1/agent/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id":1,"message":"根据知识库总结这个系统的架构和核心链路","trace_id":"demo-cli-agent"}'
```

预期 SSE 事件顺序通常为：

```text
agent_step -> tool_call -> tool_result -> agent_step -> delta -> final -> done
```

其中第一个 `agent_step` 可能是后端强制首轮检索产生的 `forced_tool_call`，随后才是 LLM 决策步骤。

记录 `done.meta.agent_run_id` 或 `final.run_id`，查询 Trace：

```bash
curl http://127.0.0.1:8000/internal/agent/runs/1
curl http://127.0.0.1:8000/internal/agent/runs/1/steps
```

查询 citations：

```bash
curl http://127.0.0.1:8080/v1/sessions/1/messages
```

## 案例 4：无证据问题

目标：展示 Agent 在检索不到证据时不会编造。

提问：

```text
文档里有没有区块链支付清结算模块？请只根据知识库回答。
```

预期：

- Agent 仍会调用 `knowledge_search`。
- 如果知识库没有相关片段，`tool_result.result.ok=true` 且 `tool_result.result.data.total` 为 `0`。
- 最终回答应说明当前知识库证据不足。
- citations 为空是合理结果。

## 案例 5：无需检索问题

目标：展示 Agent 可直接回答简单闲聊，不调用工具。

提问：

```text
你好
```

预期：

- Trace 中只有 final answer 决策步骤，或无 `tool_call`。
- 回答不应伪造引用。
- citations 为空。

## 案例 6：限定旧 RAG 文档范围

目标：确认旧 RAG 兼容显式文档范围。

```bash
curl -X POST http://127.0.0.1:8080/v1/sessions/1/messages \
  -H "Content-Type: application/json" \
  -d '{"content":"只根据这个文档总结核心内容","top_k":5,"doc_ids":[1]}'
```

预期：

- 返回 chat `task_id`。
- 任务成功后，消息 citations 的 `doc_id` 应来自指定范围。

## 演示时常用检查命令

查看 READY 文档：

```bash
curl "http://127.0.0.1:8080/v1/documents?status=READY&limit=20"
```

查看任务：

```bash
curl "http://127.0.0.1:8080/v1/tasks?limit=20"
```

查看监控概览：

```bash
curl http://127.0.0.1:8080/v1/monitor/overview
```

查看 FastAPI OpenAPI：

```bash
curl http://127.0.0.1:8000/openapi.json
```

## 演示口径

- 旧 RAG 是稳定基线：用户问题直接进入检索、Prompt 组装和回答生成。
- 新 Agent 在旧检索能力上增加工具决策层；项目文档、代码、架构、能力、上传文档、网页导入等意图会先由后端轻量路由强制执行一次 `knowledge_search`，再交给 LLM 总结。
- 当前工具只读，避免演示环境中出现写操作风险。
- Citations 统一复用原有消息引用能力，因此旧 RAG 和新 Agent 在前端引用面板的展示方式一致。
