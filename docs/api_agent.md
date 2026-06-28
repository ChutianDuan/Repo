# Agent API 文档

本文档只覆盖 MVP 演示所需的旧 RAG 与新 Agent 接口。外部演示优先走 C++ Gateway 的 `/v1/*`，持久化 Trace 调试走 FastAPI 内部 `/internal/agent/*`。

## 通用响应

普通 JSON 接口统一返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

SSE 接口返回 `text/event-stream`，每个事件形如：

```text
event: agent_step
data: {"type":"agent_step","run_id":1}

```

## 文档与建库

### 上传文档并提交 ingest

```http
POST /v1/documents
Content-Type: multipart/form-data
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | 支持 `.md`、`.txt`、`.json`、`.csv`、`.pdf`、`.docx`、`.xlsx`。 |
| `user_id` | int | 否 | 默认 `1`，用于归档和审计。 |

示例：

```bash
curl -X POST http://127.0.0.1:8080/v1/documents \
  -F "user_id=1" \
  -F "file=@./day7_demo.md"
```

响应重点字段：

```json
{
  "data": {
    "doc_id": 12,
    "task_id": "ingest-xxx",
    "status_url": "/v1/tasks/ingest-xxx"
  }
}
```

### 查询任务状态

```http
GET /v1/tasks/{task_id}
```

任务成功时 `data.state` 为 `SUCCESS`。文档完成 ingest 后进入全局 READY 知识库。

### 查询文档

```http
GET /v1/documents?status=READY&limit=100
GET /v1/documents/{doc_id}
```

## 会话与消息

### 创建会话

```http
POST /v1/sessions
Content-Type: application/json
```

请求：

```json
{
  "user_id": 1,
  "title": "MVP Demo"
}
```

响应重点字段：

```json
{
  "data": {
    "session_id": 3,
    "user_id": 1,
    "title": "MVP Demo"
  }
}
```

### 查询消息与 citations

```http
GET /v1/sessions/{session_id}/messages
```

响应中的每条 assistant message 都包含 `citations`：

```json
{
  "message_id": 22,
  "role": "assistant",
  "content": "回答正文",
  "citations": [
    {
      "citation_id": 1,
      "doc_id": 12,
      "chunk_id": 45,
      "chunk_index": 3,
      "score": 0.91,
      "snippet": "引用片段"
    }
  ],
  "meta": {
    "answer_source": "agent",
    "agent_run_id": 8,
    "citation_count": 1
  }
}
```

## 旧 RAG 接口

### 异步旧 RAG 问答

```http
POST /v1/sessions/{session_id}/messages
Content-Type: application/json
```

请求：

```json
{
  "content": "这份文档讲了什么？",
  "top_k": 5
}
```

可选限定文档范围：

```json
{
  "content": "只根据指定文档回答",
  "top_k": 5,
  "doc_ids": [12, 13]
}
```

响应重点字段：

```json
{
  "data": {
    "message_id": 21,
    "task_id": "chat-xxx",
    "state": "PENDING",
    "status_url": "/v1/tasks/chat-xxx"
  }
}
```

客户端随后轮询 `/v1/tasks/{task_id}`，成功后调用 `/v1/sessions/{session_id}/messages` 展示回答与 citations。

### 流式旧 RAG 问答

```http
POST /v1/chat/stream
Accept: text/event-stream
Content-Type: application/json
```

请求：

```json
{
  "session_id": 3,
  "content": "总结系统架构",
  "top_k": 5
}
```

SSE 事件：

| `type` | 说明 |
| --- | --- |
| `delta` | 回答增量文本。 |
| `done` | 结束事件，`meta` 包含 `assistant_message_id`、`citation_count`、`retrieval_ms` 等。 |
| `error` | 流式失败。 |

## 新 Agent 接口

### 网关流式 Agent 问答

```http
POST /v1/agent/chat/stream
Accept: text/event-stream
Content-Type: application/json
```

请求：

```json
{
  "session_id": 3,
  "message": "根据知识库总结这个系统的架构和核心链路",
  "trace_id": "demo-agent-001"
}
```

SSE 事件：

| `type` | 说明 |
| --- | --- |
| `agent_step` | Agent 决策步骤状态。 |
| `tool_call` | 工具开始调用，工具名来自当前可用只读工具列表。 |
| `tool_result` | 工具返回结果或失败信息。 |
| `delta` | 最终答案文本。MVP 当前在 Agent 完成后一次性输出。 |
| `final` | 最终回答，包含 `run_id`、`message_id`、`citations`。 |
| `done` | 流结束，`meta` 包含 `agent_run_id`、`steps_used`、`citation_count`。 |
| `error` | Agent 执行失败。 |

成功示例片段：

```text
event: tool_call
data: {"type":"tool_call","tool_name":"knowledge_search","status":"RUNNING"}

event: tool_result
data: {"type":"tool_result","tool_name":"knowledge_search","status":"SUCCESS","result":{"total":5}}

event: done
data: {"type":"done","meta":{"agent_run_id":8,"citation_count":5}}

```

### FastAPI 非流式 Agent 问答

```http
POST /internal/agent/chat
Content-Type: application/json
```

兼容路径：

```http
POST /api/agent/chat
```

请求：

```json
{
  "session_id": 3,
  "message": "根据知识库总结系统架构",
  "stream": false,
  "trace_id": "demo-agent-002"
}
```

响应：

```json
{
  "data": {
    "run_id": 8,
    "message_id": 22,
    "answer": "回答正文",
    "citations": [
      {
        "doc_id": 12,
        "chunk_id": 45,
        "chunk_index": 3,
        "score": 0.91,
        "snippet": "引用片段"
      }
    ]
  }
}
```

### 查询 Agent Run

```http
GET /internal/agent/runs/{run_id}
```

响应中的 `data.run` 包含：

- `status`: `RUNNING`、`SUCCESS`、`FAILED` 等。
- `input_json`: 用户问题。
- `output_json`: 最终答案、observations、citations。
- `total_steps` / `total_tool_calls`: 执行统计。
- `error_message`: 失败原因。

### 查询 Agent Steps 与工具调用

```http
GET /internal/agent/runs/{run_id}/steps
```

响应中的 `data.steps[]` 包含：

- `step_index`: 步骤序号。
- `decision`: `tool_call` 或 `final_answer`。
- `input_json` / `output_json`: LLM 输入输出摘要。
- `tool_calls[]`: 当前步骤下的工具调用，包含 `arguments_json`、`result_json`、`latency_ms`、`error_message`。

## Agent 工具

Agent 当前只允许只读工具。编排方式是循环决策：LLM 返回 `tool_calls` 时后端执行工具并把结果写回上下文；LLM 不再返回 `tool_calls` 时，该轮内容作为最终答案。重复的同名同参数工具调用会被跳过并记录为失败工具结果。

### `knowledge_search`

检索 indexed 知识库并返回相关 chunk。

输入 schema：

```json
{
  "query": "检索问题或改写后的查询",
  "top_k": 5
}
```

输出：

```json
{
  "results": [
    {
      "doc_id": 12,
      "document_id": 12,
      "chunk_id": 45,
      "chunk_index": 3,
      "title": "day7_demo.md",
      "content": "截断后的 chunk 内容",
      "snippet": "引用片段",
      "score": 0.91
    }
  ],
  "total": 1
}
```

错误时：

```json
{
  "results": [],
  "total": 0,
  "error": "retrieval backend unavailable"
}
```

Agent 会把带有 `doc_id`、`chunk_id`、`chunk_index` 的结果转换为 citations；缺少这些字段的工具结果只进入 Trace，不写入引用表。

### 其他只读工具

| 工具 | 说明 |
| --- | --- |
| `get_document_detail` | 根据 `document_id` 查询文档元数据。 |
| `list_ready_documents` | 列出当前可检索的 indexed 文档。 |
| `list_message_citations` | 根据 assistant `message_id` 查询已保存 citations。 |

## 常见错误

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| `session not found` | `session_id` 不存在。 | 先调用 `/v1/sessions` 创建会话。 |
| `no ready document index found` | 没有 READY 文档或 embedding 模型切换后旧索引不可用。 | 上传文档并等待 ingest 成功，必要时重新 ingest。 |
| Agent 没有工具调用 | 问题被 LLM 判断为闲聊或不依赖文档。 | 提问中明确要求“根据知识库/项目文档”。 |
| citations 为空 | 工具未检索到结果，或工具结果缺少 chunk 元数据。 | 检查 `tool_result.result.total` 和 `/internal/agent/runs/{run_id}/steps`。 |
