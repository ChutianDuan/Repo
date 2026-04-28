# 监控指标说明

监控入口为 `GET /v1/monitor/overview`，Gateway 会代理到 FastAPI 的 `/internal/monitor/overview`。指标来自 MySQL、Redis、Celery inspect、系统资源采样和 `request_metrics.extra_json`。

## 新增指标

| 指标 | 字段 | 来源 |
| --- | --- | --- |
| 文档解析耗时 | `ingest.document_parse_ms` / `latency.document_parse_ms` | ingest 阶段 `extract_text_from_document` 计时 |
| chunk 数量 | `ingest.chunk_count` / `rag.total_chunks` | ingest 产物与 `doc_chunks` 统计 |
| FAISS 检索耗时 | `quality.faiss_ms` / `latency.faiss_ms` | `search_doc_faiss_index` 计时 |
| 首 token 延迟 | `experience.ttft_ms` / `latency.ttft_ms` | SSE 第一个 delta 产生时间 |
| 总响应耗时 | `experience.e2e_latency_ms` / `latency.response_ms` | chat async / stream 端到端计时 |
| 支持最大文档大小 | `rag.max_document_size_bytes` | `MAX_DOCUMENT_SIZE_BYTES` 配置 |
| Celery 并发数 | `throughput.celery_concurrency_*` | `.env` 配置与 Celery inspect |
| Recall@K / MRR / NDCG | `quality.recall_at_k_avg` / `quality.mrr_avg` / `quality.ndcg_avg` | 带 relevance label 的 `/internal/search` 请求 |

## 检索质量评估

普通业务查询没有标准答案，因此 Recall@K、MRR 和 NDCG 默认可能为空。要记录这些指标，可以调用内部检索接口并传入人工标注的相关 chunk：

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

也可以使用 `relevant_chunk_indexes`。`scripts/e2e_all.sh` 会在完整问答后用第一条 citation 触发一次检索评估，用来验证指标链路可用。

## 上传大小

`MAX_DOCUMENT_SIZE_BYTES` 同时被 Python 内部上传接口和 C++ Gateway 上传入口使用，默认 `104857600` 字节。Drogon 的 `client_max_body_size` 仍在 `cpp_gateway/config.json` 中配置，建议保持不小于该值。
