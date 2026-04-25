# RAG 文件上传、向量检索与系统负载评估

本文说明当前系统从“上传文件”到“基于文档问答”的完整链路，并重点解释 chunk 切片、embedding 向量化、FAISS 本地索引、Top-K 召回、重排序、上下文拼接和 vLLM 调用之间的关系。

本文按目标设计说明时，假设 embedding 向量维度为 `512`，向量类型为 `float32`，索引类型为 FAISS `IndexFlatIP`。当前代码的 chunk 配置来自 [python_rag/config.py](../python_rag/config.py)，默认 `INGEST_CHUNK_SIZE=800`、`INGEST_CHUNK_OVERLAP=100`。

## 1. 总体链路

```text
文件上传
  |
  v
文件落盘 + documents 元数据入库
  |
  v
Celery ingest 异步任务
  |
  |-- 文档解析 / 文本抽取
  |-- chunk 切片
  |-- doc_chunks 入库
  |-- chunk embedding 向量化
  |-- FAISS 本地索引构建
  |-- document_indexes 写入索引元数据
  v
文档 READY

用户提问
  |
  v
问题 embedding 向量化
  |
  v
FAISS Top-K 或 Candidate-K 召回
  |
  v
重排序 rerank
  |
  v
选择最终上下文 chunks
  |
  v
拼接 prompt
  |
  v
发送给 vLLM / OpenAI-compatible LLM
  |
  v
回答 + citations 落库
```

整个系统可以拆成两条主链路：

| 链路 | 触发时机 | 主要成本 | 主要产物 |
| --- | --- | --- | --- |
| Ingest 建库链路 | 文件上传后 | 文档解析、chunk、embedding、FAISS 写索引 | `doc_chunks`、`.faiss`、mapping JSON、`document_indexes` |
| Query 问答链路 | 用户提问时 | query embedding、FAISS 检索、rerank、vLLM 推理 | answer、citations、messages |

## 2. 上传与 Ingest 过程

### 2.1 文件上传

用户通过前端或 API 上传文档后，外部入口会完成几件事：

1. 校验文件类型和基本请求参数。
2. 计算文件 `sha256`，用于去重和追踪。
3. 将原始文件保存到本地 `data/uploads`。
4. 在 MySQL `documents` 表中写入文件元数据，包括文件名、MIME、大小、存储路径、状态等。
5. 提交 Celery ingest 异步任务，避免上传接口被后续耗时处理阻塞。

### 2.2 文本抽取

Celery Worker 会根据文件类型抽取纯文本。抽取结果必须非空，否则文档会进入失败状态。

文本抽取完成后，系统进入切片阶段。

### 2.3 Chunk 切片

当前项目使用简单字符切片：

- `chunk_size = 800`
- `chunk_overlap = 100`
- 实际步长 `step = chunk_size - chunk_overlap = 700`

切片的目的不是压缩文本，而是让长文档变成适合 embedding 和 LLM 上下文拼接的小片段。overlap 的作用是保留相邻片段之间的上下文连续性，减少答案刚好跨 chunk 边界时的召回失败。

粗略估算 chunk 数：

```text
如果文档字符数 <= chunk_size:
  chunk_count = 1

否则:
  chunk_count ≈ ceil((字符数 - chunk_size) / (chunk_size - overlap)) + 1
```

在默认配置下，可以近似写成：

```text
chunk_count ≈ 文档字符数 / 700
```

示例：

| 文档纯文本规模 | 估算 chunk 数 |
| ---: | ---: |
| 10,000 字符 | 约 15 |
| 100,000 字符 | 约 143 |
| 1,000,000 字符 | 约 1,429 |
| 10,000,000 字符 | 约 14,286 |

切片完成后，每个 chunk 会写入 `doc_chunks` 表，保留 `doc_id`、`chunk_index`、`text`、`tokens_est` 等字段。

### 2.4 Chunk embedding 向量化

每个 chunk 会被送入 embedding 模型，生成一个固定长度向量。你当前按 `512` 维设计，可以理解为：

```text
chunk_text -> embedding_model -> float32[512]
```

向量化阶段有几个关键点：

| 关键点 | 说明 |
| --- | --- |
| 同一模型 | 文档 chunk 和用户问题必须使用同一个 embedding 模型。 |
| 同一向量空间 | 切换模型后，旧索引必须重建，否则 query 向量和 doc 向量不在同一语义空间。 |
| 同一归一化策略 | 当前支持 `EMBEDDING_NORMALIZE=true`，归一化后使用内积检索基本等价于余弦相似度。 |
| query/document prefix | 如果模型需要区分检索任务中的 query 和 document，应固定配置 `EMBEDDING_QUERY_PREFIX` 和 `EMBEDDING_DOCUMENT_PREFIX`。 |
| 批处理 | 当前 `EMBEDDING_BATCH_SIZE=32`，批量 embedding 可以显著提高吞吐。 |

512 维 `float32` 向量的原始大小：

```text
512 * 4 bytes = 2048 bytes ≈ 2 KB / chunk
```

所以仅 FAISS 向量部分的存储规模为：

| chunk 数 | 向量原始大小 |
| ---: | ---: |
| 10,000 | 约 19.5 MB |
| 100,000 | 约 195 MB |
| 1,000,000 | 约 1.91 GB |
| 10,000,000 | 约 19.1 GB |

注意：这是纯向量大小，不包含 MySQL 中的 chunk 文本、mapping JSON、索引文件额外结构、日志和任务元数据。

### 2.5 FAISS 本地索引

当前项目使用 FAISS `IndexFlatIP`：

```text
index = faiss.IndexFlatIP(dim)
index.add(vectors)
```

含义：

- `Flat`：精确检索，不做近似聚类或图索引。
- `IP`：inner product，内积相似度。
- 当 embedding 已 L2 normalize 时，内积排序基本等价于 cosine similarity 排序。

系统会为每个文档写两个本地文件：

| 文件 | 作用 |
| --- | --- |
| `data/indexes/doc_{doc_id}.faiss` | FAISS 向量索引文件 |
| `data/indexes/doc_{doc_id}_mapping.json` | FAISS 行号到 `chunk_id`、`doc_id`、`chunk_index`、文本内容的映射 |

同时，`document_indexes` 表会记录：

- `doc_id`
- `index_type`
- `embedding_model`
- `dimension`
- `index_path`
- `mapping_path`
- `chunk_count`
- `status`

这里保存 `embedding_model` 很重要。查询时系统会检查当前 embedding 模型是否和建索引时一致。如果不一致，应拒绝查询并提示重新 ingest。

## 3. 提问与检索过程

### 3.1 问题 embedding

用户输入问题后，系统先把问题向量化：

```text
question -> embedding_model -> float32[512]
```

这一步必须和文档 chunk 使用同一个模型、同一个归一化策略。否则 FAISS 找到的最近邻没有稳定语义意义。

问题 embedding 的成本通常远小于文档 ingest，因为一次请求只需要编码一个 query；但在高并发下，query embedding 仍然会成为共享模型服务的 QPS 压力来源。

### 3.2 FAISS Top-K 召回

FAISS 根据 query vector 在目标文档索引中搜索相似 chunk：

```text
scores, indices = index.search(query_vector, top_k)
```

返回内容包括：

- `chunk_id`
- `chunk_index`
- `score`
- `content`

如果直接把 FAISS 的 `top_k` 结果送给 vLLM，链路简单、延迟低，但排序质量完全依赖 embedding 模型。embedding 检索擅长“粗召回”，但不一定擅长精细排序，尤其在以下场景容易出错：

- 问题很短，但文档中相似表述很多。
- chunk 语义接近，但只有少数片段真正回答问题。
- 领域术语、数字、否定句、条件约束较多。
- top-1 相似度高，但实际是背景信息，不是答案依据。

因此建议把 FAISS 的返回数量分成两层：

| 参数 | 建议含义 | 常见范围 |
| --- | --- | --- |
| `candidate_top_k` | FAISS 粗召回候选数 | 20 到 50 |
| `final_top_k` | rerank 后送入 vLLM 的 chunk 数 | 3 到 5 |

也就是说，不建议只检索 3 个再重排 3 个。更合理的是先召回 20 到 50 个候选，再用 reranker 选出最值得进入 prompt 的 3 到 5 个。

### 3.3 Rerank 重排序

重排序是本系统质量提升的关键点之一。

embedding 检索做的是双塔向量相似度：

```text
score = similarity(embed(question), embed(chunk))
```

它的优点是快，可以提前离线算好文档向量；缺点是 query 和 chunk 在编码后才比较，交互不充分。

reranker 通常使用 cross-encoder 或专门的排序模型，对每个候选 pair 做更细粒度判断：

```text
rerank_score = reranker(question, chunk)
```

它的优点是排序质量更高，因为模型能同时看到问题和候选 chunk；缺点是每次查询都要对多个候选重新计算，成本明显高于 FAISS。

推荐流程：

```text
1. FAISS 召回 candidate_top_k = 30
2. 对 30 个候选构造 pair: (question, chunk)
3. reranker 批量打分
4. 按 rerank_score 从高到低排序
5. 去重、过滤低分片段
6. 取 final_top_k = 3 到 5
7. 拼接给 vLLM
```

可以采用三类重排序策略：

| 策略 | 质量 | 延迟 | 适用场景 |
| --- | --- | --- | --- |
| 仅 FAISS score 排序 | 中 | 最低 | demo、小文档、低成本优先 |
| Cross-encoder reranker | 高 | 中高 | 正式 RAG 问答、准确率优先 |
| LLM rerank | 高但成本大 | 高 | 少量高价值请求、复杂推理场景 |

如果引入 cross-encoder reranker，建议保留 FAISS 分数用于观测，但最终排序以 reranker 分数为主。也可以做混合分数：

```text
final_score = alpha * normalized_faiss_score + beta * rerank_score
```

在业务上更推荐先简单使用 reranker 分数排序，只有当 reranker 对某些场景不稳定时再引入融合分数。

当前实现已经新增 cross-encoder reranker：`top_k` 表示最终送入 prompt 的 chunk 数，`CHAT_CANDIDATE_TOP_K` 表示 FAISS 粗召回候选数。系统会保留 `faiss_score`、`rerank_score` 和 `original_rank`，便于分析 rerank 前后的排序变化。

### 3.4 上下文拼接

重排序后，系统会把最终 chunk 拼接成 context block，再和用户问题组成 prompt。

当前系统有 `CHAT_MAX_CHUNK_CHARS=1000`，用于限制单个 chunk 进入 prompt 的最大字符数。假设 `final_top_k=5`：

```text
最大上下文字符数 ≈ 5 * 1000 = 5000 字符
```

最终 prompt 大致包含：

- system 指令
- 检索到的 chunk 内容
- chunk 元数据，例如 `doc_id`、`chunk_index`、`score`
- 用户问题

控制 `final_top_k` 的意义很大：它直接影响 vLLM 的 prompt tokens、TTFT、显存占用和吞吐。

### 3.5 发送给 vLLM

vLLM 承担最终回答生成。对 vLLM 来说，主要负载来自：

- prompt tokens：上下文越长，prefill 越慢。
- completion tokens：回答越长，decode 越慢。
- 并发流式请求数：影响排队、TTFT 和显存 KV cache。
- 模型大小和量化方式：模型越大，吞吐越低，显存需求越高。

RAG 系统里，检索阶段通常不是最大瓶颈。真正的线上瓶颈常常是：

```text
vLLM 推理 > reranker > embedding > FAISS
```

前提是 FAISS 索引已经缓存或索引规模不大。如果每次查询都从磁盘读取大型 FAISS 文件，FAISS I/O 会成为额外瓶颈。

## 4. 512 维向量下的容量估算

### 4.1 每个 chunk 的基础成本

按 `512` 维、`float32` 计算：

```text
vector_bytes_per_chunk = 512 * 4 = 2048 bytes ≈ 2 KB
```

但系统实际存储不只有向量：

| 存储项 | 估算 |
| --- | ---: |
| FAISS 向量 | 约 2 KB / chunk |
| mapping JSON | 约 1 到 4 KB / chunk，取决于文本长度和语言 |
| MySQL `doc_chunks.text` | 约 1 到 4 KB / chunk，取决于文本长度和编码 |
| 元数据、索引、JSON 结构开销 | 数百 bytes 到数 KB / chunk |

因此，比较务实的总磁盘估算是：

```text
每个 chunk 约 4 到 10 KB
```

如果中文文本较多，UTF-8 下单字符可能占 3 bytes，mapping JSON 又重复保存了一份 chunk 内容，实际更接近上限。

### 4.2 按 chunk 数估算磁盘

| chunk 总数 | 纯 FAISS 向量 | 估算总磁盘 |
| ---: | ---: | ---: |
| 10,000 | 约 19.5 MB | 约 40 到 100 MB |
| 100,000 | 约 195 MB | 约 0.4 到 1 GB |
| 1,000,000 | 约 1.91 GB | 约 4 到 10 GB |
| 10,000,000 | 约 19.1 GB | 约 40 到 100 GB |

这些数字只用于容量规划。真实值要以 `data/indexes`、MySQL 表大小和上传原文大小为准。

### 4.3 按文档规模估算

使用默认切片参数时：

```text
chunk_count ≈ 文档字符数 / 700
```

| 单文档纯文本字符数 | chunk 数 | FAISS 向量大小 | 估算总存储 |
| ---: | ---: | ---: | ---: |
| 10,000 | 约 15 | 约 30 KB | 小于 1 MB |
| 100,000 | 约 143 | 约 286 KB | 约 1 MB 级别 |
| 1,000,000 | 约 1,429 | 约 2.8 MB | 约 6 到 15 MB |
| 10,000,000 | 约 14,286 | 约 27.9 MB | 约 60 到 150 MB |

因此，512 维本身并不会让存储爆炸。真正需要关注的是：

- mapping JSON 和 MySQL 是否重复保存大段文本。
- 是否每个文档一个 FAISS 文件，文件数量是否过多。
- 查询时是否反复从磁盘加载 FAISS 文件。
- 是否需要跨文档全局检索。

## 5. 检索计算量估算

FAISS `IndexFlatIP` 是精确暴力检索，单次 query 的主要计算量近似为：

```text
计算量 ≈ chunk_count * 512 次乘加
```

示例：

| 单次搜索 chunk 数 | 近似乘加次数 | 评价 |
| ---: | ---: | --- |
| 10,000 | 512 万 | 很轻 |
| 100,000 | 5120 万 | CPU 可接受，热缓存下通常不是主瓶颈 |
| 1,000,000 | 5.12 亿 | 开始明显，需要关注延迟和内存带宽 |
| 10,000,000 | 51.2 亿 | 不适合继续用纯 Flat 精确搜索做在线查询 |

对当前“按文档检索”的设计来说，如果一次只查一个文档，即使系统总文档很多，只要单文档 chunk 数不大，FAISS 搜索压力仍然可控。

如果未来要“跨所有文档检索”，总 chunk 数会直接进入搜索复杂度，此时需要考虑：

- 全局 FAISS 索引。
- IVF / HNSW / PQ 等近似索引。
- 按用户、租户、知识库分片。
- 热索引常驻内存。
- GPU FAISS 或专门向量数据库。

## 6. 系统负载规模评估

下面按当前实现和目标放大后的架构分别评估。

### 6.1 当前实现的实际上限

当前 ingest 建索引时已经显式读取该文档的全部 chunks，不再受到 `list_chunks_by_doc_id` 默认 `limit=200` 的限制。

在单文档本地 FAISS Flat 索引设计下：

| 项 | 规模判断 |
| --- | --- |
| 单文档索引 chunk 数 | 主要受文档大小、内存和磁盘限制 |
| 单文档 FAISS 向量大小 | 约 `chunk_count * 2 KB` |
| FAISS 检索压力 | 中小文档较低，大文档取决于 chunk 数和索引加载方式 |
| 主要瓶颈 | embedding、reranker、vLLM、任务队列和 FAISS 文件 I/O |

这意味着项目已经能完整索引大文档，但如果单文档 chunk 很多，后续仍应增加 FAISS index cache，避免每次查询都从磁盘加载索引。

### 6.2 推荐规模

保持 `512` 维、`IndexFlatIP`、本地文件索引时，建议按以下规模理解：

| 规模 | chunk 总量 | 适合程度 | 建议 |
| --- | ---: | --- | --- |
| 小规模 | 1 万以内 | 很适合 | 当前架构足够，重点优化 vLLM。 |
| 中小规模 | 1 万到 10 万 | 适合 | 建议缓存热点 FAISS index，增加 rerank。 |
| 中规模 | 10 万到 100 万 | 可做但要优化 | 避免每次磁盘读索引，考虑全局索引、分片或 ANN。 |
| 大规模 | 100 万到 1000 万 | 当前 Flat 架构压力较大 | 推荐 IVF/HNSW、向量库、索引常驻内存、分布式切分。 |
| 超大规模 | 1000 万以上 | 不建议用当前单机 Flat 方案 | 需要专门检索架构和容量设计。 |

### 6.3 在线问答负载

一次普通 RAG 问答的耗时大致由以下部分组成：

```text
总延迟 ≈ query_embedding_ms
       + faiss_search_ms
       + rerank_ms
       + prompt_build_ms
       + vLLM_prefill_ms
       + vLLM_decode_ms
```

通常：

- `prompt_build_ms` 很小。
- `faiss_search_ms` 在中小规模下较小。
- `query_embedding_ms` 取决于 embedding 模型和部署方式。
- `rerank_ms` 取决于 candidate 数量和 reranker 模型。
- `vLLM_prefill_ms` 与 prompt 长度强相关。
- `vLLM_decode_ms` 与输出长度强相关。

如果 `candidate_top_k=30`、`final_top_k=5`，负载特征是：

| 阶段 | 输入规模 | 压力 |
| --- | --- | --- |
| query embedding | 1 个问题 | 低到中 |
| FAISS | N 个 chunk 向量 | 中小规模下低 |
| rerank | 30 个 question/chunk pair | 中到高 |
| vLLM | 约 5 个 chunk 的上下文 + 问题 | 高 |

因此，实际并发能力一般由 vLLM 和 reranker 决定，而不是 512 维 FAISS 本身决定。

在单机部署、单个 vLLM 实例、普通 7B 到 14B 级模型的前提下，可以粗略按以下方式规划：

| 场景 | 粗略能力判断 |
| --- | --- |
| 演示 / 个人使用 | 1 到 5 个并发会话通常可承受。 |
| 小团队内部使用 | 5 到 20 个活跃并发需要关注 vLLM 显存、TTFT 和队列。 |
| 更高并发 | 需要多 vLLM 实例、请求排队、限流、缓存、缩短上下文和输出长度。 |

这个并发估算不能替代压测，因为模型大小、GPU、量化方式、上下文长度和输出长度都会显著改变结果。项目已有 [performance_test_guide.md](./performance_test_guide.md)，建议用固定文档、固定问题集和固定 `top_k` 做压测留档。

### 6.4 Ingest 负载

Ingest 的主要压力来自文档 embedding，而不是 FAISS 写索引。

单个文档的 ingest 时间大致为：

```text
ingest_time ≈ text_extract
            + chunk_count / embedding_throughput
            + faiss_build
            + mysql_write
```

其中 embedding throughput 取决于：

- embedding 模型大小。
- CPU 还是 GPU。
- batch size。
- 是否远程 OpenAI-compatible embedding 服务。
- 文本长度和 tokenizer 成本。

512 维只影响输出向量大小，不直接代表 embedding 模型很轻。真正的计算量由 embedding 模型本身决定。

建议：

- ingest worker 并发不要盲目拉高，先从 `1` 到 `2` 开始压测。
- embedding 服务独立部署时，要限制 Celery 并发，避免同时提交太多大文档。
- 大文档 ingest 建议分批 embedding，并记录每批耗时。
- 切换 embedding 模型或 prefix 后，必须重建所有索引。

## 7. 重排序和向量化的工程建议

### 7.1 向量化建议

1. 固定 embedding 模型版本，并写入索引元数据。
2. 固定 `512` 维后，查询前校验 query vector 维度和 index 维度一致。
3. 开启 normalize 后使用 `IndexFlatIP`，让分数更接近 cosine similarity。
4. 文档和问题使用一致的 query/document prefix 策略。
5. 对 embedding 质量做离线评估：Recall@K、MRR、NDCG、Top-1 命中率。
6. 建立真实业务 QA 验证集，不只看向量相似度。

### 7.2 Rerank 建议

1. 将 `candidate_top_k` 和 `final_top_k` 拆开。
2. 建议初始配置：`candidate_top_k=30`，`final_top_k=5`。
3. reranker 使用 batch 推理，避免 30 个候选逐条串行请求。
4. reranker 输出分数和 FAISS 分数都写入日志或 metrics，方便分析误召回。
5. 对低 rerank 分数结果设置阈值，必要时进入 low-confidence prompt。
6. 对相同内容、相邻 chunk、重复 chunk 做去重或合并。
7. 保留 citations，最终回答必须能追溯到具体 chunk。

### 7.3 Prompt 拼接建议

1. final chunk 数控制在 3 到 5。
2. 单 chunk 最大字符数控制在 800 到 1200。
3. chunk 中保留必要元数据，但不要把过多 JSON 结构塞进 prompt。
4. 如果答案经常跨 chunk，可以在 rerank 后补充相邻 chunk，而不是单纯提高 final_top_k。
5. 对长问题和长上下文分别记录 tokens，观察 TTFT 是否恶化。

## 8. 需要优先修正或增强的点

| 优先级 | 建议 | 原因 |
| --- | --- | --- |
| 已完成 | 修正 ingest 建索引只取 200 chunks 的限制 | 大文档可以完整进入 FAISS。 |
| 已完成 | 增加 cross-encoder reranker | 支持基于 question/chunk pair 的语义重排序。 |
| 已完成 | 拆分 `candidate_top_k` 和 `final_top_k` | 粗召回和最终上下文使用不同数量。 |
| P1 | 缓存热点 FAISS index | 避免每次查询都从磁盘读 `.faiss` 文件。 |
| 已完成 | 记录 rerank_ms、candidate_top_k、final_top_k | 便于定位延迟和质量问题。 |
| P2 | mapping JSON 不重复保存全文或改为按 chunk_id 回表 | 可降低磁盘占用。 |
| P2 | 大规模时引入 ANN 索引或向量数据库 | Flat 精确检索不适合千万级在线检索。 |

## 9. 结论

在 `512` 维 embedding 下，向量本身的存储成本并不高，约 `2 KB / chunk`。如果按默认 `800` 字符切片、`100` overlap，一个百万字符文档大约会产生 `1429` 个 chunk，纯向量只有约 `2.8 MB`。因此，中小规模 RAG 系统的主要瓶颈不是向量存储，而是 embedding 模型吞吐、reranker 延迟、vLLM 上下文长度和生成吞吐。

当前本地 FAISS Flat 架构可以较稳地支撑 1 万到 10 万 chunk 级别的检索；到 10 万到 100 万 chunk 时，需要做索引缓存、分片或 ANN 优化；超过百万级后，应认真考虑全局向量检索架构，而不是继续依赖每次读取本地 Flat 索引文件。

质量上，最关键的是两点：第一，embedding 必须稳定、一致、可评估；第二，rerank 必须是真正基于 question/chunk pair 的语义重排序，而不是简单按 FAISS 分数或原顺序截断。一个更合理的生产配置是：FAISS 先召回 `20` 到 `50` 个候选，reranker 重排后取 `3` 到 `5` 个 chunk 拼接给 vLLM。
