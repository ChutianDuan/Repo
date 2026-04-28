export type ServiceState = "ok" | "warn" | "error" | "unknown";

export interface SystemMetrics {
  cpu_percent?: number | null;
  memory_percent?: number | null;
  memory_used_gb?: number | null;
  memory_total_gb?: number | null;
  disk_percent?: number | null;
  network_rx_kbps?: number | null;
  network_tx_kbps?: number | null;
}

export interface GpuMetrics {
  id: number;
  name: string;
  util_percent?: number | null;
  memory_used_mb?: number | null;
  memory_total_mb?: number | null;
  temperature?: number | null;
}

export interface ServiceHealthMap {
  mysql: ServiceState;
  redis: ServiceState;
  worker: ServiceState;
  llm: ServiceState;
  embedding: ServiceState;
  api: ServiceState;
}

export interface QueueMetrics {
  pending: number;
  running: number;
  failed: number;
  worker_count?: number | null;
  worker_concurrency_configured?: number | null;
  worker_concurrency_observed?: number | null;
}

export interface LatencyMetrics {
  api_ms?: number | null;
  ttft_ms?: number | null;
  chat_ms?: number | null;
  response_ms?: number | null;
  retrieval_ms?: number | null;
  faiss_ms?: number | null;
  ingest_ms?: number | null;
  document_parse_ms?: number | null;
}

export interface LatencyDistribution {
  last?: number | null;
  avg?: number | null;
  p50?: number | null;
  p95?: number | null;
  p99?: number | null;
}

export interface ExperienceMetrics {
  window_seconds?: number;
  chat_samples?: number;
  ingest_samples?: number;
  ttft_ms: LatencyDistribution;
  e2e_latency_ms: LatencyDistribution;
  ingest_ready_ms: LatencyDistribution;
}

export interface IngestMetrics {
  document_parse_ms: LatencyDistribution;
  chunk_count: LatencyDistribution;
}

export interface CostMetrics {
  prompt_tokens_avg?: number | null;
  prompt_tokens_total?: number | null;
  completion_tokens_avg?: number | null;
  completion_tokens_total?: number | null;
  cost_per_request_usd?: number | null;
  cost_per_document_usd?: number | null;
  chat_cost_total_usd?: number | null;
  ingest_cost_total_usd?: number | null;
}

export interface ThroughputMetrics {
  qps?: number | null;
  concurrent_sessions?: number | null;
  worker_queue_depth?: number | null;
  active_sse_connections?: number | null;
  celery_concurrency_configured?: number | null;
  celery_concurrency_observed?: number | null;
  celery_pool?: string | null;
}

export interface QualityMetrics {
  error_rate?: number | null;
  timeout_rate?: number | null;
  retrieval_ms: LatencyDistribution;
  faiss_ms: LatencyDistribution;
  citation_count_avg?: number | null;
  no_context_ratio?: number | null;
  retrieval_eval_samples?: number | null;
  recall_at_k_avg?: number | null;
  mrr_avg?: number | null;
  ndcg_avg?: number | null;
}

export interface RagMetrics {
  documents_ready: number;
  total_chunks: number | null;
  max_document_size_bytes?: number | null;
  top_k?: number;
  retrieval_mode?: string;
}

export interface MonitorOverview {
  system: SystemMetrics;
  gpu: GpuMetrics[];
  services: ServiceHealthMap;
  queue: QueueMetrics;
  latency: LatencyMetrics;
  rag: RagMetrics;
  ingest: IngestMetrics;
  experience: ExperienceMetrics;
  cost: CostMetrics;
  throughput: ThroughputMetrics;
  quality: QualityMetrics;
  samples?: {
    total?: number | null;
    chat?: number | null;
    ingest?: number | null;
  };
  updated_at: string;
  source?: "monitor-api" | "health-fallback";
}

export interface MetricPoint {
  label: string;
  cpu?: number | null;
  gpu?: number | null;
  api_ms?: number | null;
  throughput?: number | null;
}
