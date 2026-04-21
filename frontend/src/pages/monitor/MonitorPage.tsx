import type { MetricPoint, MonitorOverview } from "../../types/monitor";
import { MetricCard } from "../../components/common/MetricCard";
import { PageTitle } from "../../components/common/PageTitle";
import { SectionCard } from "../../components/common/SectionCard";
import { MetricsChartPanel } from "../../components/monitor/MetricsChartPanel";
import { ResourceOverviewCards } from "../../components/monitor/ResourceOverviewCards";
import { ServiceHealthPanel } from "../../components/monitor/ServiceHealthPanel";
import { formatDateTime, formatNumber } from "../../utils/format";

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

      <SectionCard title="Metrics Panels" description="无第三方图表依赖，使用轻量趋势条展示近端变化。">
        <MetricsChartPanel points={points} />
      </SectionCard>
    </div>
  );
}
