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
}

export interface LatencyMetrics {
  api_ms?: number | null;
  chat_ms?: number | null;
  retrieval_ms?: number | null;
  ingest_ms?: number | null;
}

export interface RagMetrics {
  documents_ready: number;
  total_chunks: number | null;
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
