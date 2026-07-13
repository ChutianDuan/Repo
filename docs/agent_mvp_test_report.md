# 一次 Agent MVP 联调如何证明“会检索、会失败、会收敛”

[返回文档地图](README.md)

> 历史验证快照：初始验证日期为 2026-05-27，后续同步到 2026-07-01。文中的 run ID、服务健康状态、模型地址和通过数量只描述当时环境，不代表当前进程状态。

Agent 演示最容易只验证成功路径：模型返回答案，页面出现文字，于是宣布“Agent 可用”。这份报告选择了更严格的证据标准，要求同一套执行循环同时证明四件事：需要知识时会检索，不需要时不滥用工具，没有证据时不编造，工具失败时能留下 Trace 并降级回答。

## 先看结论

在这次快照中，四个目标场景均有自动化覆盖：能回答、能按需调用 `knowledge_search`、能在无证据时说明知识库证据不足、能在工具返回 `error` 时记录失败并降级回答。

本轮还将 LLM 默认运行方式改为远端 OpenAI-compatible API：`scripts/start_vllm.sh` 默认只检查 API 连通性，不再因为存在 `VLLM_MODEL_PATH` 自动启动本地 vLLM；本地 vLLM 仅在显式设置 `LLM_RUNTIME=local_vllm` 时使用。

## 第一次加固：工具协议与循环上限（2026-06-28）

Agent hardening 已补充以下行为，并由自动化测试覆盖：

- 工具执行使用 `asyncio.wait_for` 强制应用工具自身 `timeout_ms`，超时会写入 FAILED tool call。
- 工具入参在执行前按当前 schema 做轻量校验；缺必填字段、类型不匹配、越界或额外字段会记录为失败工具结果。
- 工具返回统一为 `{"ok": bool, "error": string | null, "data": object}`，Trace、SSE `tool_result` 和 LLM 工具消息均使用该结构。
- Agent Run Trace 写入 `AGENT_VERSION`、`PROMPT_VERSION`，并汇总 run 级 `prompt_tokens`、`completion_tokens`、`total_tokens`。
- `max_steps` 达到上限时不再直接抛出 Agent 失败，而是进入一次无工具最终回答阶段，基于已有观察返回降级结论。

最新聚焦验证命令：

```bash
python -m pytest \
  tests/test_agent_orchestrator.py \
  tests/test_agent_trace_service.py \
  tests/test_knowledge_search_tool.py \
  tests/test_get_document_detail_tool.py \
  tests/test_list_ready_documents_tool.py \
  tests/test_citation_tools.py \
  tests/test_agent_api.py \
  tests/test_agent_streaming_service.py

python -m compileall python_rag/app/agent
```

## 第二次加固：检索不再只靠提示词（2026-07-01）

Agent 的“是否检索”不再只依赖系统提示约束。`agent_runner.py` 增加轻量检索意图路由：问题命中项目文档、代码、架构、能力、上传文档、网页导入、embedding、索引等意图时，后端会在首轮 LLM 调用前强制执行一次 `knowledge_search`，Trace 决策记为 `forced_tool_call`，然后再让 LLM 基于工具结果总结。

对应回归测试覆盖了以下行为：

- `根据项目文档总结系统架构` 会先执行 `knowledge_search`，即使 fake LLM 本身没有主动返回 `tool_calls`。
- 问候类问题仍不触发强制检索。
- 原有工具调用、错误、超时、非法参数、重复调用和 `max_steps` 降级逻辑保持可用。

## 改动落在了哪里

| 文件 | 变更 |
| --- | --- |
| `python_rag/app/agent/orchestrator.py` | 补充 Agent 工具使用策略；将工具结果中的 `error` 识别为失败工具调用，写入 failed Trace，并把错误传给后续 LLM 降级回答。 |
| `frontend/src/app/App.tsx` | Agent Trace 展示补充“无需检索，直接回答”和“工具失败：原因”，工具失败后显示降级生成状态。 |
| `tests/test_agent_orchestrator.py` | 补齐 Agent MVP 四个联调场景的回归测试。 |
| `scripts/start_vllm.sh` | 默认 `LLM_RUNTIME=api`，只在 `LLM_RUNTIME=local_vllm` 时启动本地 vLLM。 |
| `.env.example` | 默认 LLM 配置改为远端 API：`LLM_RUNTIME=api`、`LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`、`LLM_MODEL=glm-4.7-flash`。 |
| `README.md`, `docs/environment.md`, `scripts/README.md` | 同步 API 模式启动和排障说明。 |

## 四个场景分别证明什么

| 场景 | 用户输入 | 预期 | 验证结果 |
| --- | --- | --- | --- |
| 1. 需要检索 | `根据项目文档总结系统架构` | 调用 `knowledge_search` 后回答 | 通过。测试确认后端检索路由先执行 `knowledge_search`，Trace 写入 `forced_tool_call` step 和 tool_call，随后 LLM 基于工具结果输出最终回答。 |
| 2. 不需要检索 | `你好` | 不调用工具，直接回答 | 通过。测试确认 `knowledge_search` 未被调用，只有 final_answer step。 |
| 3. 检索不到 | `文档里有没有区块链支付模块？` | 调用 `knowledge_search`，说明知识库证据不足 | 通过。测试确认工具调用成功但返回 `data.total=0`，最终回答包含“证据不足”。 |
| 4. 工具失败 | `knowledge_search timeout` | 记录失败，并返回降级说明 | 通过。测试确认工具结果 `error=knowledge_search timeout` 被写为 FAILED tool_call，后续回答为降级说明。 |

## 为什么数据库 Trace 比控制台日志更可信

- Agent Run：`trace_service.create_run()` 创建 `agent_runs`，结束时 `finish_run()` / `fail_run()` 写终态、输出、错误和 finished_at。
- Agent Step：每轮 LLM 决策写入 `agent_steps`，包括 step_index、input_json、output_json、decision、token 和 latency。
- Tool Call：每次工具调用写入 `agent_tool_calls`，成功用 SUCCESS；工具异常、超时、参数校验失败或工具结果 `ok=false` / `error` 非空用 FAILED，并写入 `error_message`、`result_json`、`result_preview`。
- 查询入口：`GET /api/agent/runs/{run_id}` 和 `GET /api/agent/runs/{run_id}/steps` 可展示完整 Trace，steps 响应包含对应 tool_calls。
- 表结构：`db/004_create_agent_tables.sql` 提供 `agent_runs`、`agent_steps`、`agent_tool_calls`。

## 模型运行方式也属于测试条件

运行时 `.env` 需要使用 API 配置，不再指向本地 `127.0.0.1:9000/v1`：

```bash
LLM_RUNTIME=api
LLM_ENABLE=true
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MIMO_API_KEY=your-api-key
LLM_MODEL=glm-4.7-flash
```

改完 `.env` 后需要重启 FastAPI/Gateway。`bash scripts/start_vllm.sh` 在 API 模式下只检查 `${LLM_BASE_URL}/models`，不会启动本地模型。

## 当时实际执行的验证

```bash
pytest tests/test_agent_orchestrator.py tests/test_agent_trace_service.py tests/test_knowledge_search_tool.py tests/test_agent_streaming_service.py tests/test_agent_api.py
```

结果：22 passed。

```bash
npm --prefix frontend run typecheck
```

结果：通过，`tsc --noEmit` 无错误。

```bash
bash -n scripts/start_vllm.sh
```

结果：通过，脚本语法正确。

```bash
pytest
```

结果：未通过完整收集，原因是当前 Python 环境缺少 `numpy`，阻断 `tests/test_chunking_service.py` 和 `tests/test_reranker_service.py` 的 import；这不是本次 Agent 改动引入的问题。

## 当时的 Live 环境状态

当时切换并重启服务后记录的 live 环境状态如下。它们是验收证据，不是当前健康检查：

- `.env` 使用 `LLM_RUNTIME=api`、`LLM_BASE_URL=https://api.xiaomimimo.com/v1`、`LLM_MODEL=mimo-v2.5-pro`，API key 已配置但未在报告中展示。
- `bash scripts/start_vllm.sh` 返回 `LLM runtime=api`、`local vLLM will not be started`、`LLM API /models reachable`。
- `GET http://127.0.0.1:8000/internal/health` 返回 `data.ok=true`。
- `GET http://127.0.0.1:8080/health` 返回 `data.ok=true`。
- 当时数据库中存在 READY / indexed 文档，可用于真实检索。
- 为避免 live 验收被 reranker 缺失权重下载阻塞，`.env` 设置 `RERANK_DOWNLOAD_IF_MISSING=false`，并保留 `RERANK_FALLBACK_TO_FAISS=true`（历史配置名；当前默认 LanceDB 召回路径下表示按召回顺序回退）。

## 当时的 Live 验收结果

| 场景 | 验收方式 | run_id | 结果 |
| --- | --- | --- | --- |
| 需要检索 | `POST /api/agent/chat` | 8 | SUCCESS；2 steps；`knowledge_search` SUCCESS，返回 10 条；决策为 `tool_call -> final_answer`。 |
| 不需要检索 | `POST /api/agent/chat` | 9 | SUCCESS；1 step；无 tool_calls；决策为 `final_answer`。 |
| 检索不到 | `POST /api/agent/chat` | 10 | SUCCESS；2 steps；`knowledge_search` SUCCESS，回答明确说明未找到区块链支付模块相关文档。 |
| 工具失败 | 受控失败工具 + 真实 DB Trace | 11 | SUCCESS；2 steps；`knowledge_search` 写入 FAILED，`error_message=knowledge_search timeout`，最终返回降级说明。 |

说明：公开 `/api/agent/chat` 当前没有安全的工具失败注入参数，因此工具失败场景使用受控失败工具执行真实 `AgentOrchestrator` 与真实数据库 Trace 验证，避免破坏线上检索配置。

## 这份报告没有证明什么

- 没有证明高并发 SSE 的稳定性或容量上限。
- 没有证明模型在真实业务 QA 集上的答案质量。
- 没有证明历史 live 环境仍然在线。
- 没有覆盖 Gateway handler 级自动化测试。

重新验证当前版本时，应以仓库现有测试和统一启动入口为准：

```bash
python -m pytest tests
python -m compileall python_rag tests
bash scripts/ci_smoke.sh
START_FRONTEND=true bash scripts/start_all.sh start
bash scripts/start_all.sh status
```
