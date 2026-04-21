import type { AppRoute } from "../../app/router";
import { HealthDot } from "../common/HealthDot";
import type { MonitorOverview } from "../../types/monitor";
import { formatBytesGb, formatPercent } from "../../utils/format";

interface AppHeaderProps {
  route: AppRoute;
  overview: MonitorOverview;
  searchScope: string;
  onNavigate: (route: AppRoute) => void;
  onRefresh: () => void;
  refreshing: boolean;
}

export function AppHeader({ route, overview, searchScope, onNavigate, onRefresh, refreshing }: AppHeaderProps) {
  const gpuUsage = overview.gpu.length > 0 ? overview.gpu[0]?.util_percent : null;
  const serviceDots = [
    ["MySQL", overview.services.mysql] as const,
    ["Redis", overview.services.redis] as const,
    ["Worker", overview.services.worker] as const,
  ];

  return (
    <header className="app-header">
      <div className="app-header__brand" onClick={() => onNavigate("workspace")} role="button" tabIndex={0}>
        <span className="brand-mark">R</span>
        <div>
          <strong>RAG Workbench</strong>
          <small>{route === "workspace" ? "Document QA Workspace" : "Supporting Console"}</small>
        </div>
      </div>

      <div className="app-header__scope">
        <span>Search Scope</span>
        <strong>{searchScope}</strong>
      </div>

      <div className="app-header__metrics" aria-label="system summary">
        <span>CPU {formatPercent(overview.system.cpu_percent)}</span>
        <span>GPU {formatPercent(gpuUsage)}</span>
        <span>RAM {formatBytesGb(overview.system.memory_used_gb, overview.system.memory_total_gb)}</span>
        <span>Queue {overview.queue.pending + overview.queue.running}</span>
        {serviceDots.map(([label, state]) => (
          <HealthDot key={label} label={label} state={state} compact />
        ))}
      </div>

      <div className="app-header__actions">
        <button type="button" className="button-ghost" onClick={() => onNavigate("documents")}>
          Upload
        </button>
        <button type="button" className="button-secondary" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? "Checking" : "Refresh"}
        </button>
      </div>
    </header>
  );
}
