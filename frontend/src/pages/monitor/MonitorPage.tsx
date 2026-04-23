import type { MetricPoint, MonitorOverview } from "../../types/monitor";
import { MetricCard } from "../../components/common/MetricCard";
import { PageTitle } from "../../components/common/PageTitle";
import { SectionCard } from "../../components/common/SectionCard";
import { MetricsChartPanel } from "../../components/monitor/MetricsChartPanel";
import { ResourceOverviewCards } from "../../components/monitor/ResourceOverviewCards";
import { ServiceHealthPanel } from "../../components/monitor/ServiceHealthPanel";
import { formatCurrencyUsd, formatDateTime, formatDurationMs, formatNumber, formatRatio } from "../../utils/format";

interface MonitorPageProps {
  overview: MonitorOverview;
  points: MetricPoint[];
  monitorError: string | null;
  onRefreshMonitor: () => void;
}

export function MonitorPage({ overview, points, monitorError, onRefreshMonitor }: MonitorPageProps) {
  return (
    <div className="monitor-page page-stack">
      <PageTitle
        eyebrow="Operations"
        title="Monitor"
        description="克制的工程监控页：资源、服务健康、队列、延迟和 RAG 关键指标。"
        action={
          <div className="monitor-toolbar">
            <span>Last Update: {formatDateTime(overview.updated_at)}</span>
            <button type="button" onClick={onRefreshMonitor}>
              Refresh
            </button>
          </div>
        }
      />

      {monitorError ? <div className="notice-box">{monitorError}</div> : null}

      <SectionCard title="Resource Cards" description="CPU / GPU / 内存 / 磁盘 / 网络资源摘要。">
        <ResourceOverviewCards overview={overview} />
      </SectionCard>

      <SectionCard title="Service Status" description="MySQL、Redis、Worker、Embedding、LLM、API 健康情况。">
        <ServiceHealthPanel overview={overview} />
      </SectionCard>

      <div className="summary-grid">
        <MetricCard label="Pending Tasks" value={formatNumber(overview.queue.pending)} tone="warn" />
        <MetricCard label="Running Tasks" value={formatNumber(overview.queue.running)} />
        <MetricCard label="Failed Tasks" value={formatNumber(overview.queue.failed)} tone={overview.queue.failed > 0 ? "error" : "default"} />
        <MetricCard label="API Latency" value={`${overview.latency.api_ms ?? "--"}ms`} />
        <MetricCard label="Ready Docs" value={formatNumber(overview.rag.documents_ready)} />
        <MetricCard label="Total Chunks" value={overview.rag.total_chunks === null ? "--" : formatNumber(overview.rag.total_chunks)} />
      </div>

      <SectionCard title="Experience" description="TTFT、端到端延迟分位数和 ingest 就绪时间。">
        <div className="summary-grid">
          <MetricCard label="TTFT P50" value={formatDurationMs(overview.experience.ttft_ms.p50)} />
          <MetricCard label="TTFT P95" value={formatDurationMs(overview.experience.ttft_ms.p95)} />
          <MetricCard label="E2E P50" value={formatDurationMs(overview.experience.e2e_latency_ms.p50)} />
          <MetricCard label="E2E P95" value={formatDurationMs(overview.experience.e2e_latency_ms.p95)} />
          <MetricCard label="E2E P99" value={formatDurationMs(overview.experience.e2e_latency_ms.p99)} />
          <MetricCard label="Ingest Ready P50" value={formatDurationMs(overview.experience.ingest_ready_ms.p50)} />
        </div>
      </SectionCard>

      <SectionCard title="Cost" description="请求和文档成本基于 provider usage 或估算 token，并结合可配置单价计算。">
        <div className="summary-grid">
          <MetricCard label="Prompt Tokens Avg" value={formatNumber(overview.cost.prompt_tokens_avg)} />
          <MetricCard label="Completion Tokens Avg" value={formatNumber(overview.cost.completion_tokens_avg)} />
          <MetricCard label="Cost / Request" value={formatCurrencyUsd(overview.cost.cost_per_request_usd)} />
          <MetricCard label="Cost / Document" value={formatCurrencyUsd(overview.cost.cost_per_document_usd)} />
          <MetricCard label="Chat Cost Total" value={formatCurrencyUsd(overview.cost.chat_cost_total_usd)} />
          <MetricCard label="Ingest Cost Total" value={formatCurrencyUsd(overview.cost.ingest_cost_total_usd)} />
        </div>
      </SectionCard>

      <SectionCard title="Throughput" description="QPS、并发会话数、Worker 队列深度和活跃 SSE 连接。">
        <div className="summary-grid">
          <MetricCard label="QPS" value={overview.throughput.qps === null || overview.throughput.qps === undefined ? "--" : overview.throughput.qps.toFixed(3)} />
          <MetricCard label="Concurrent Sessions" value={formatNumber(overview.throughput.concurrent_sessions)} />
          <MetricCard label="Worker Queue Depth" value={formatNumber(overview.throughput.worker_queue_depth)} />
          <MetricCard label="Active SSE" value={formatNumber(overview.throughput.active_sse_connections)} />
          <MetricCard label="Worker Count" value={formatNumber(overview.queue.worker_count)} />
        </div>
      </SectionCard>

      <SectionCard title="Quality" description="错误率、超时率、检索耗时、引用数量和无上下文占比。">
        <div className="summary-grid">
          <MetricCard label="Error Rate" value={formatRatio(overview.quality.error_rate)} tone={overview.quality.error_rate && overview.quality.error_rate > 0.05 ? "error" : "default"} />
          <MetricCard label="Timeout Rate" value={formatRatio(overview.quality.timeout_rate)} tone={overview.quality.timeout_rate && overview.quality.timeout_rate > 0.02 ? "warn" : "default"} />
          <MetricCard label="Retrieval P50" value={formatDurationMs(overview.quality.retrieval_ms.p50)} />
          <MetricCard label="Retrieval P95" value={formatDurationMs(overview.quality.retrieval_ms.p95)} />
          <MetricCard label="Citation Avg" value={formatNumber(overview.quality.citation_count_avg)} />
          <MetricCard label="No Context Ratio" value={formatRatio(overview.quality.no_context_ratio)} />
        </div>
      </SectionCard>

      <SectionCard title="Metrics Panels" description="无第三方图表依赖，使用轻量趋势条展示近端变化。">
        <MetricsChartPanel points={points} />
      </SectionCard>
    </div>
  );
}
