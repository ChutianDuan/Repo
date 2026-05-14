# 代码审核与完成度评估

审核日期：2026-05-11

本次重点看 C++ Gateway 和 `python_rag` 两部分，同时顺带检查了启动脚本、数据库脚本、前端构建入口和现有文档。

## 1. 总体结论

当前项目已经超过普通 RAG demo：上传、异步 ingest、全局 READY 知识库、BM25 + FAISS + RRF + CrossEncoder rerank、异步/流式问答、citations、任务状态、监控、前端工作台、鉴权和限流都已经形成闭环。

按不同目标评估：

| 目标 | 完成度 | 判断 |
| --- | ---: | --- |
| 作品集 / 面试展示 | 85% | 架构分层、链路完整度和监控留档已经很有说服力。 |
| 小团队内部 alpha | 70% | 能跑完整业务流，但还缺自动化测试、部署封装和高并发保护。 |
| 生产级多租户系统 | 55% | 鉴权、限流已有雏形，但租户隔离、审计、索引扩展和运维体系还需要补齐。 |

## 2. 主要发现

| 优先级 | 发现 | 影响 | 建议 |
| --- | --- | --- | --- |
| 已修复 | 流式 chat 对 `user_message_id` 的校验弱于异步 chat。现在已新增 `python_rag/modules/chat/validation.py`，异步提交、Celery 运行时和 SSE 运行时复用 `validate_chat_user_message()`。 | 已避免 assistant/system 消息被直接当作用户问题再次生成，也避免错误改写非 user 消息状态。 | 后续可以继续扩展状态机约束，例如只允许 `PENDING` / `PROCESSING` 的 user message 进入生成链路。 |
| P1 | 检索按文档 fan-out，并且每次请求从磁盘读取 FAISS 和 mapping。全局检索最多取 1000 个 READY 文档，见 `python_rag/modules/retrieval/service.py:145` 到 `python_rag/modules/retrieval/service.py:150`；每个文档都会调用检索，见 `python_rag/modules/retrieval/service.py:233` 到 `python_rag/modules/retrieval/service.py:257`；底层每次 `faiss.read_index` 和 `json.load`，见 `python_rag/modules/retrieval/faiss_service.py:56` 到 `python_rag/modules/retrieval/faiss_service.py:60`。 | 文档数量或单文档 chunk 数上来后，磁盘 I/O、JSON 解析和 fan-out 延迟会快速放大。 | 短期加 LRU/TTL index cache；中期做知识库级或分片 FAISS；长期评估 ANN / 向量数据库。 |
| 部分缓解 | SSE 网关每个流式请求仍会使用一个 detached OS thread 和阻塞 libcurl 读取上游，但现在已用 `GATEWAY_MAX_STREAMS` 限制并发流数量。 | 并发资源不再无限增长；高并发下仍会按活跃流占用线程。 | 后续改为受控线程池、连接计数和超时回收；或者使用支持流式回调的异步 HTTP 客户端。 |
| 已修复 | Gateway 转发 GET query 时原来手动拼接参数，没有 URL encode。现在 `cpp_gateway/src/main.cc` 已补 `urlEncode()`、`appendQueryParam()` 和 `buildPathWithQuery()`。 | 特殊字符不会再破坏转发语义。 | 后续如果 GET 路由继续增加，复用该 helper。 |
| P2 | Gateway 的 MySQL / Redis 连接仍以 `cpp_gateway/config.json` 为准，安全配置和部分路径来自 `.env`。 | 部署时容易误以为 `.env` 已经覆盖全部配置，导致环境漂移。 | 将 config.json 生成化，或让启动脚本按 `.env` 渲染 config。 |
| 已修复 | `cpp_gateway/src/StreamChatService.*` 是旧版残留，CMake 当前编译的是 `cpp_gateway/src/handlers/StreamChatHandler.*`。 | 已删除旧文件，降低维护误读概率。 | 后续保持 StreamChat 只维护 `handlers/StreamChatHandler.*`。 |
| 基础完成 | 自动化测试基本缺位，目前主要依赖脚本和手工 E2E。 | 已新增 pytest 基础测试和 `scripts/ci_smoke.sh`，覆盖 chat 校验、chunking、rerank fallback、retrieval fan-out 和 stream error。 | 继续补 FastAPI contract、Gateway 编译/集成测试和真实 E2E。 |

## 3. 模块完成度

### Gateway

已完成：

- 对外路由统一收口到 `/v1/*` 和 `/health`。
- 文件上传负责类型校验、SHA-256、落盘、写入 `documents` 并提交 ingest job。
- 支持 API Key 鉴权、Redis IP/User 限流、CORS 和健康检查聚合。
- 支持异步 chat 和 SSE chat 代理。

待补：

- 统一错误响应格式，目前 Gateway 自身错误和 Python 透传错误结构不完全一致。
- request id / trace id 透传、访问审计、关键请求日志脱敏。
- 配置收敛、SSE 并发保护。
- C++ 层自动化构建验证和最小 handler 测试。

### python_rag

已完成：

- 文档解析覆盖 `.md`、`.txt`、`.json`、`.csv`、`.pdf`、`.docx`、`.xlsx`。
- ingest 支持 chunk、embedding、FAISS 构建、索引元数据和任务状态。
- 检索链路支持 BM25、FAISS、RRF、CrossEncoder rerank 和指标记录。
- chat 支持异步 Celery 和 OpenAI-compatible streaming，回答、citations、metrics 能落库。
- 监控聚合已经覆盖系统资源、队列、RAG 数据、延迟、成本估算和检索质量指标。

待补：

- FAISS/mapping 缓存、全局索引或分片索引。
- 真实业务 QA 标注集，用固定数据集评估 Recall@K、MRR、NDCG 和答案可用性。
- 更多 contract 测试，尤其是模型不可用、索引不匹配、空检索、重复上传。

### 前端与文档

已完成：

- 已有工作台页面：Workspace、Documents、Tasks、Monitor、Settings。
- README、容量说明、性能测试、鉴权限流、监控指标、embedding 微调都有独立文档。

待补：

- 单独的 API contract 文档，列出 Gateway 与 FastAPI 内部接口的请求/响应样例。
- 运维 Runbook，覆盖启动、停机、日志、常见故障和恢复流程。
- 测试策略文档，定义每次改动必须跑哪些检查。

## 4. 后续路线图

| 阶段 | 目标 | 任务 |
| --- | --- | --- |
| 已完成 | 修掉明显一致性风险 | 已统一 chat message 校验、清理旧 `StreamChatService.*`、补充 Gateway query encode helper。 |
| 基础完成 | 提升可回归性 | 已增加 Python pytest 基础集，并补 `scripts/ci_smoke.sh`；后续继续扩展 contract/E2E。 |
| P1 / 近期 | 提升部署稳定性 | 生成化 Gateway config；补 Docker Compose；记录 request id；统一错误 envelope。 |
| P2 / 中期 | 提升检索规模 | 加 FAISS/mapping cache；设计全局或分片索引；减少 mapping JSON 重复保存全文。 |
| P2 / 中期 | 提升质量评估 | 建业务 QA 集；固定 benchmark；记录每轮模型、top_k、candidate_top_k、rerank 配置。 |
| P3 / 后续 | 生产化 | 多租户隔离、审计日志、向量库/ANN、后台重建索引、灰度模型切换。 |

## 5. 本次验证

已执行：

```bash
python3 -m compileall python_rag
python3 -m pytest tests
bash scripts/ci_smoke.sh
bash -n scripts/init_db.sh
bash -n scripts/start_api.sh
bash -n scripts/start_worker.sh
bash -n scripts/start_all.sh
```

结果：以上检查通过。`scripts/ci_smoke.sh` 在本机因没有 `npm` 跳过前端构建，并打印 warning。

未完成：

- `cmake -S cpp_gateway -B cpp_gateway/build-local -DCMAKE_BUILD_TYPE=Debug` 因本机未配置 Drogon 包失败，错误是找不到 `DrogonConfig.cmake` / `drogon-config.cmake`。
- `npm run build` 因本机没有 `npm` 命令无法执行。
