import type { HealthSnapshot } from "../types/api";
import type { DocumentListItem } from "../types/document";
import type { ChatMessage } from "../types/message";
import type { MetricPoint, MonitorOverview, ServiceState } from "../types/monitor";
import type { TaskRecord, TaskStatus } from "../types/task";
import { nowIso } from "../utils/format";
import { summarizeGpuMetrics } from "../utils/gpu";

export type PendingAction =
  | "health"
  | "user"
  | "upload"
  | "web-upload"
  | "session"
  | "chat"
  | "messages"
  | `delete-document-${number}`
  | null;

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function parsePositiveInteger(value: string, fieldName: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${fieldName} 必须是正整数`);
  }
  return parsed;
}

export function normalizeTopK(value: number): number {
  if (!Number.isFinite(value)) {
    return 3;
  }
  return Math.max(1, Math.min(10, Math.round(value)));
}

export function normalizeDocumentState(value: string | null | undefined): string {
  return String(value || "").trim().toLowerCase();
}

export function isIndexedDocument(document: DocumentListItem): boolean {
  const indexStatus = normalizeDocumentState(document.index_status);
  const status = normalizeDocumentState(document.status);
  return indexStatus === "indexed" || indexStatus === "ready" || status === "indexed" || status === "ready";
}

export function isFailedDocument(document: DocumentListItem): boolean {
  const indexStatus = normalizeDocumentState(document.index_status);
  const status = normalizeDocumentState(document.status);
  return indexStatus === "failed" || indexStatus === "failure" || status === "failed" || status === "failure";
}

export function isProcessingDocument(document: DocumentListItem): boolean {
  if (isIndexedDocument(document) || isFailedDocument(document)) {
    return false;
  }
  const indexStatus = normalizeDocumentState(document.index_status);
  const status = normalizeDocumentState(document.status);
  return ["not_indexed", "parsing", "parsed", "indexing", "pending", "uploaded", "processing", "ingesting"].includes(indexStatus || status);
}

function serviceState(ok: boolean | undefined): ServiceState {
  if (ok === true) {
    return "ok";
  }
  if (ok === false) {
    return "error";
  }
  return "unknown";
}

export function isTerminalTask(state: string): boolean {
  return ["SUCCESS", "FAILURE", "FAILED"].includes(state);
}

export function getChunkCount(meta: Record<string, unknown> | null | undefined): number | null {
  const value = meta?.chunk_count;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function buildFallbackOverview(
  health: HealthSnapshot | null,
  tasks: TaskRecord[],
  documents: DocumentListItem[],
  apiLatencyMs: number | null,
  topK: number,
): MonitorOverview {
  const pending = tasks.filter((task) => task.state === "PENDING").length;
  const running = tasks.filter((task) => !isTerminalTask(task.state) && task.state !== "PENDING").length;
  const failed = tasks.filter((task) => task.state === "FAILURE" || task.state === "FAILED").length;
  const readyDocuments = documents.filter(isIndexedDocument);
  const knownChunks = readyDocuments
    .map((document) => document.chunks)
    .filter((value): value is number => typeof value === "number");

  return {
    system: {
      cpu_percent: null,
      memory_percent: null,
      memory_used_gb: null,
      memory_total_gb: null,
      disk_percent: null,
    },
    gpu: [],
    services: {
      mysql: serviceState(health?.mysql?.ok),
      redis: serviceState(health?.redis?.ok),
      worker: tasks.length > 0 ? "ok" : "unknown",
      llm: "unknown",
      embedding: "unknown",
      api: serviceState(health?.ok),
    },
    queue: {
      pending,
      running,
      failed,
      worker_count: null,
      worker_concurrency_configured: null,
      worker_concurrency_observed: null,
    },
    latency: {
      api_ms: apiLatencyMs,
      ttft_ms: null,
      chat_ms: null,
      response_ms: null,
      retrieval_ms: null,
      faiss_ms: null,
      ingest_ms: null,
      document_parse_ms: null,
    },
    rag: {
      documents_ready: readyDocuments.length,
      total_chunks: knownChunks.length > 0 ? knownChunks.reduce((sum, value) => sum + value, 0) : null,
      max_document_size_bytes: null,
      top_k: topK,
      retrieval_mode: "document",
    },
    ingest: {
      document_parse_ms: {},
      chunk_count: {},
    },
    experience: {
      ttft_ms: {},
      e2e_latency_ms: {},
      ingest_ready_ms: {},
    },
    cost: {
      prompt_tokens_avg: null,
      prompt_tokens_total: null,
      completion_tokens_avg: null,
      completion_tokens_total: null,
      cost_per_request_usd: null,
      cost_per_document_usd: null,
      chat_cost_total_usd: null,
      ingest_cost_total_usd: null,
    },
    throughput: {
      qps: null,
      concurrent_sessions: null,
      worker_queue_depth: pending + running,
      active_sse_connections: null,
      celery_concurrency_configured: null,
      celery_concurrency_observed: null,
      celery_pool: null,
    },
    quality: {
      retrieval_ms: {},
      faiss_ms: {},
      error_rate: null,
      timeout_rate: null,
      citation_count_avg: null,
      no_context_ratio: null,
      retrieval_eval_samples: null,
      recall_at_k_avg: null,
      mrr_avg: null,
      ndcg_avg: null,
    },
    samples: {
      total: tasks.length,
      chat: null,
      ingest: null,
    },
    updated_at: nowIso(),
    source: "health-fallback",
  };
}

export function taskRecordFromStatus(
  status: TaskStatus,
  existing: TaskRecord | undefined,
  defaults: Partial<TaskRecord>,
): TaskRecord {
  return {
    task_id: status.task_id,
    type: defaults.type || existing?.type || "system",
    entity_type: defaults.entity_type || existing?.entity_type || "system",
    entity_id: defaults.entity_id ?? existing?.entity_id ?? 0,
    db_task_id: defaults.db_task_id ?? existing?.db_task_id,
    state: status.state,
    progress: status.progress,
    meta: status.meta ?? null,
    error: status.error ?? null,
    created_at: existing?.created_at || defaults.created_at || nowIso(),
    updated_at: nowIso(),
  };
}

export function buildLocalMessage(
  sessionId: number,
  role: ChatMessage["role"],
  content: string,
  status: string,
): ChatMessage {
  const timestamp = nowIso();
  return {
    message_id: -Math.floor(Date.now() + Math.random() * 1000000),
    session_id: sessionId,
    role,
    content,
    status,
    citations: [],
    meta: {},
    created_at: timestamp,
    updated_at: timestamp,
  };
}

export function buildMetricPoint(
  nextOverview: MonitorOverview,
  fallbackThroughput: number,
): MetricPoint {
  const timestamp = new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  return {
    label: timestamp,
    cpu: nextOverview.system.cpu_percent,
    gpu: summarizeGpuMetrics(nextOverview.gpu).util_percent,
    api_ms: nextOverview.latency.api_ms,
    throughput: nextOverview.throughput.qps ?? fallbackThroughput,
  };
}
