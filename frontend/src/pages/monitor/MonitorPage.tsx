import type { MetricPoint, MonitorOverview } from "../../types/monitor";
import { MetricCard } from "../../components/common/MetricCard";
import { PageTitle } from "../../components/common/PageTitle";
import { SectionCard } from "../../components/common/SectionCard";
import { ServiceHealthPanel } from "../../components/monitor/ServiceHealthPanel";
import { formatBytes, formatDateTime, formatDurationMs, formatNumber } from "../../utils/format";

interface MonitorPageProps {
  overview: MonitorOverview;
  points: MetricPoint[];
  monitorError: string | null;
  onRefreshMonitor: () => void;
}

export function MonitorPage({ overview, points, monitorError, onRefreshMonitor }: MonitorPageProps) {
  const latestPoint = points[points.length - 1];

  return (
    <div className="monitor-page page-stack">
      <PageTitle
        eyebrow="运行状态"
        title="状态"
        description="这里保留项目运行所需的基础状态，方便确认文档索引和问答链路是否可用。"
        action={
          <div className="monitor-toolbar">
            <span>更新 {formatDateTime(overview.updated_at)}</span>
            <button type="button" onClick={onRefreshMonitor}>
              刷新
            </button>
          </div>
        }
      />

      {monitorError ? <div className="notice-box">{monitorError}</div> : null}

      <SectionCard title="服务" description="API、Worker、Embedding 和 LLM 都可用时，完整 RAG 链路才可正常工作。">
        <ServiceHealthPanel overview={overview} />
      </SectionCard>

      <div className="summary-grid">
        <MetricCard label="可检索文档" value={formatNumber(overview.rag.documents_ready)} />
        <MetricCard label="切片数" value={overview.rag.total_chunks === null ? "--" : formatNumber(overview.rag.total_chunks)} />
        <MetricCard label="等待任务" value={formatNumber(overview.queue.pending)} tone={overview.queue.pending > 0 ? "warn" : "default"} />
        <MetricCard label="运行任务" value={formatNumber(overview.queue.running)} />
        <MetricCard label="失败任务" value={formatNumber(overview.queue.failed)} tone={overview.queue.failed > 0 ? "error" : "default"} />
        <MetricCard label="API 延迟" value={`${overview.latency.api_ms ?? "--"}ms`} />
        <MetricCard label="检索 P95" value={formatDurationMs(overview.quality.retrieval_ms.p95)} />
        <MetricCard label="最大文档" value={formatBytes(overview.rag.max_document_size_bytes)} />
      </div>

      <SectionCard title="最近请求" description={`最近采样 ${latestPoint?.label || "--"}，用于判断当前问答是否有明显延迟波动。`}>
        <div className="summary-grid">
          <MetricCard label="TTFT" value={formatDurationMs(overview.experience.ttft_ms.last ?? overview.experience.ttft_ms.p50)} />
          <MetricCard label="端到端" value={formatDurationMs(overview.experience.e2e_latency_ms.last ?? overview.experience.e2e_latency_ms.p50)} />
          <MetricCard label="检索" value={formatDurationMs(overview.quality.retrieval_ms.last ?? overview.quality.retrieval_ms.p50)} />
          <MetricCard label="引用数" value={formatNumber(overview.quality.citation_count_avg ?? null)} />
        </div>
      </SectionCard>
    </div>
  );
}
