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

## GPU 监控范围

GPU 监控默认不再无条件统计整机所有 GPU。后端会优先读取 `MONITOR_GPU_IDS`；如果为空，则从 `VLLM_CUDA_VISIBLE_DEVICES`、`API_CUDA_VISIBLE_DEVICES`、`WORKER_CUDA_VISIBLE_DEVICES` 和 `PYTHON_CUDA_VISIBLE_DEVICES` 自动推断当前服务使用的物理 GPU 编号。

```bash
# 只监控 0、1、6 号 GPU
MONITOR_GPU_IDS=0,1,6

# 显示整机所有 GPU
MONITOR_GPU_IDS=all
```

接口会返回 `gpu_scope`，用于确认当前 GPU 监控范围和来源。前端资源卡对返回的 `gpu` 列表做聚合：使用率取平均，显存取总和。

## 检索质量评估

普通业务查询没有标准答案，因此 Recall@K、MRR 和 NDCG 默认可能为空。要记录这些指标，可以调用内部检索接口并传入人工标注的相关 chunk。`doc_id` 可以省略，省略时会检索全局 READY 文档；传入 `doc_id` 或 `doc_ids` 时只评估指定范围：

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
