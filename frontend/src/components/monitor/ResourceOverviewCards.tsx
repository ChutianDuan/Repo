import type { MonitorOverview } from "../../types/monitor";
import { MetricCard } from "../common/MetricCard";
import { formatBytesGb, formatNumber, formatPercent } from "../../utils/format";
import { summarizeGpuMetrics } from "../../utils/gpu";

interface ResourceOverviewCardsProps {
  overview: MonitorOverview;
}

export function ResourceOverviewCards({ overview }: ResourceOverviewCardsProps) {
  const gpuSummary = summarizeGpuMetrics(overview.gpu);

  return (
    <div className="resource-overview-cards">
      <MetricCard label="CPU Usage" value={formatPercent(overview.system.cpu_percent)} />
      <MetricCard
        label="Memory Usage"
        value={formatPercent(overview.system.memory_percent)}
        detail={formatBytesGb(overview.system.memory_used_gb, overview.system.memory_total_gb)}
      />
      <MetricCard
        label="GPU Usage"
        value={formatPercent(gpuSummary.util_percent)}
        detail={gpuSummary.label}
      />
      <MetricCard
        label="GPU Memory"
        value={
          gpuSummary.memory_used_mb !== null && gpuSummary.memory_total_mb !== null
            ? `${formatNumber(gpuSummary.memory_used_mb)} / ${formatNumber(gpuSummary.memory_total_mb)} MB`
            : "--"
        }
      />
      <MetricCard label="Disk" value={formatPercent(overview.system.disk_percent)} />
      <MetricCard
        label="Network"
        value={
          overview.system.network_rx_kbps || overview.system.network_tx_kbps
            ? `${formatNumber(overview.system.network_rx_kbps)} / ${formatNumber(overview.system.network_tx_kbps)} KB/s`
            : "--"
        }
        detail="rx / tx"
      />
    </div>
  );
}
