# 从系统健康到检索质量：怎样读懂 RAG 监控指标

[返回文档地图](README.md)

CPU 正常不代表回答链路正常，LLM 可用也不代表检索质量可信。RAG 监控至少要同时回答四类问题：服务是否活着、请求慢在哪里、任务是否堆积、检索结果是否有质量依据。

监控入口是 `GET /v1/monitor/overview`，Gateway 代理到 FastAPI `/internal/monitor/overview`。数据来自系统资源采样、MySQL、Redis、Celery inspect 和 `request_metrics`。

## 四层指标模型

```mermaid
flowchart LR
    H[Health<br/>进程与依赖] --> T[Throughput<br/>请求与队列]
    T --> L[Latency<br/>解析/召回/重排/生成]
    L --> Q[Quality<br/>Recall/MRR/NDCG/Citations]
```

- **Health** 适合回答“服务是否可访问”，不证明模型或 LanceDB 一定可用。
- **Throughput** 观察请求、任务队列和 Worker 并发。
- **Latency** 把总耗时拆到 ingest、retrieval、rerank、TTFT 和端到端生成。
- **Quality** 需要标注数据；没有 relevance label 时不应该制造 Recall@K。

## 关键字段从哪里来

| 关注点 | 字段 | 数据来源与解释 |
| --- | --- | --- |
| 文档解析 | `ingest.document_parse_ms` / `latency.document_parse_ms` | `extract_text_from_document` 计时 |
| Chunk 产物 | `ingest.chunk_count` / `rag.total_chunks` | ingest task 与 `doc_chunks` 统计 |
| 检索总耗时 | `quality.retrieval_ms` / `latency.retrieval_ms` | query embedding、召回、回表和 rerank 端到端 |
| LanceDB 召回 | `extra_json.lancedb_ms` / retrieval `metrics.lancedb_ms` | `search_lancedb_index` 单请求计时 |
| 兼容 FAISS | `quality.faiss_ms` / `latency.faiss_ms` | 历史兼容字段；默认 LanceDB 路径通常为空 |
| 首 token | `experience.ttft_ms` / `latency.ttft_ms` | 第一个生成 delta 出现时间 |
| 端到端响应 | `experience.e2e_latency_ms` / `latency.response_ms` | async / stream 完整请求 |
| 队列能力 | `throughput.celery_concurrency_*` | `.env` 与 Celery inspect |
| 检索质量 | `quality.recall_at_k_avg` / `mrr_avg` / `ndcg_avg` | 仅来自带 relevance label 的检索评估 |
| 上传边界 | `rag.max_document_size_bytes` | `MAX_DOCUMENT_SIZE_BYTES` 配置，不是实际上传量 |

`request_metrics` 表不存在或没有数据时，聚合会退化为系统资源和任务计数。空字段表示缺少观测样本，不等于数值为零。

## GPU 范围必须显式可解释

后端优先读取 `MONITOR_GPU_IDS`；为空时从 vLLM、API、Worker 和 Python 的 `*_CUDA_VISIBLE_DEVICES` 推断服务实际使用的物理 GPU。

```bash
# 只观察本项目使用的 4、5 号卡
MONITOR_GPU_IDS=4,5

# 明确需要整机视角时
MONITOR_GPU_IDS=all
```

响应中的 `gpu_scope` 用来解释监控范围及来源。前端对 GPU 使用率取平均、显存取总和；这适合工作台摘要，不应替代逐卡诊断。

## 检索质量为什么默认可能为空

普通问题没有“哪个 chunk 必须相关”的标准答案，所以系统无法从一次业务查询自动得出 Recall、MRR 或 NDCG。要记录质量指标，必须显式提供人工标注的相关 chunk：

```bash
curl -X POST http://127.0.0.1:8000/internal/search \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": 1,
    "query": "这份文档讲了什么？",
    "top_k": 5,
    "relevant_chunk_ids": [123]
  }'
```

也可以传 `relevant_chunk_indexes`。`scripts/e2e_all.sh` 会使用问答产生的第一条 citation 触发一次链路验证，但这种自举方式只证明指标管道可用，不能替代独立人工标注集。

## 怎样从症状定位指标

| 症状 | 先看 | 下一步 |
| --- | --- | --- |
| 上传长时间未完成 | queue depth、parse ms、chunk count | Worker 日志、文档解析与 embedding |
| 首字很慢 | TTFT、retrieval ms | 区分检索慢还是 LLM 首 token 慢 |
| retrieval 突然升高 | LanceDB ms、rerank ms、候选数 | 检查过滤范围、MySQL 回表和模型初始化 |
| 回答快但引用差 | Recall/MRR/NDCG、citations | 固定 QA 集，比较 embedding 与 rerank |
| GPU 0% | `gpu_scope` | 确认监控的是物理卡还是当前服务可见卡 |

不要用单个总耗时替代分段指标，也不要把一次低延迟当成容量结论。性能测试的采样方法见 [性能测试指南](performance_test_guide.md)。

## 上传大小是配置边界，不是容量证明

`MAX_DOCUMENT_SIZE_BYTES` 同时约束 Python 上传接口和 Gateway 上传入口，默认是 `104857600` 字节。Drogon 的 `client_max_body_size` 必须不小于它。

允许上传 100 MB 只证明请求体可以被接受，并不证明解析、chunk、embedding、索引时间或内存占用满足目标。文档容量需要结合 [Ingest 与 Retrieval 容量设计](rag_ingest_retrieval_capacity.md) 阅读。

## 当前观测空白

- 没有独立 LanceDB health，只能从 indexed 文档和真实 retrieval activity 推断使用情况。
- LLM health 不是 Gateway `/health` 的组成部分。
- 没有标注集时，检索质量字段为空是正确行为。
- 本地进程内 metrics 不等于生产级时序数据库，重启与多实例聚合需要额外设计。
