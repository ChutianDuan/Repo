import type { MonitorOverview } from "../../types/monitor";
import { MetricCard } from "../common/MetricCard";
import { formatBytesGb, formatNumber, formatPercent } from "../../utils/format";

interface ResourceOverviewCardsProps {
  overview: MonitorOverview;
}

export function ResourceOverviewCards({ overview }: ResourceOverviewCardsProps) {
  const primaryGpu = overview.gpu[0];

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
        value={formatPercent(primaryGpu?.util_percent)}
        detail={primaryGpu?.name || "No GPU telemetry"}
      />
      <MetricCard
        label="GPU Memory"
        value={
          primaryGpu?.memory_used_mb && primaryGpu.memory_total_mb
            ? `${formatNumber(primaryGpu.memory_used_mb)} / ${formatNumber(primaryGpu.memory_total_mb)} MB`
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
