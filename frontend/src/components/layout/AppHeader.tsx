import {
  ArrowClockwise,
  GearSix,
  Pulse,
} from "@phosphor-icons/react";
import type { AppRoute } from "../../app/router";
import type { HealthSnapshot } from "../../types/api";
import type { MonitorOverview, ServiceState } from "../../types/monitor";

interface AppHeaderProps {
  route: AppRoute;
  overview: MonitorOverview;
  health: HealthSnapshot | null;
  onNavigate: (route: AppRoute) => void;
  onRefresh: () => void;
  refreshing: boolean;
}

const PRIMARY_NAV: Array<{ route: AppRoute; label: string }> = [
  { route: "documents", label: "Documents" },
  { route: "workspace", label: "Sessions" },
  { route: "tasks", label: "Runs" },
  { route: "monitor", label: "Monitor" },
];

function healthState(value: boolean | undefined): ServiceState {
  if (value === true) return "ok";
  if (value === false) return "error";
  return "unknown";
}

function ServiceSignal({ label, state }: { label: string; state: ServiceState }) {
  return (
    <span className={`service-signal service-signal--${state}`} title={`${label}: ${state}`}>
      <span aria-hidden="true" />
      {label}
    </span>
  );
}

export function AppHeader({
  route,
  overview,
  health,
  onNavigate,
  onRefresh,
  refreshing,
}: AppHeaderProps) {
  return (
    <header className="app-header app-header--workbench">
      <button
        type="button"
        className="workbench-brand"
        onClick={() => onNavigate("workspace")}
        aria-label="Open RAG Workbench"
      >
        <span className="workbench-brand__mark"><Pulse size={18} weight="bold" /></span>
        <strong>RAG Workbench</strong>
      </button>

      <nav className="top-navigation" aria-label="Primary navigation">
        {PRIMARY_NAV.map((item) => (
          <button
            key={item.route}
            type="button"
            className={route === item.route ? "top-navigation__item is-active" : "top-navigation__item"}
            onClick={() => onNavigate(item.route)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="header-runtime" aria-label="Runtime health">
        <ServiceSignal label="Gateway" state={health ? "ok" : "unknown"} />
        <ServiceSignal label="FastAPI" state={healthState(health?.python?.ok)} />
        <ServiceSignal label="Worker" state={overview.services.worker} />
        <button
          type="button"
          className="header-icon-button"
          onClick={onRefresh}
          disabled={refreshing}
          aria-label="Refresh runtime status"
          title="Refresh runtime status"
        >
          <ArrowClockwise size={17} className={refreshing ? "is-spinning" : ""} />
        </button>
        <button
          type="button"
          className={route === "settings" ? "header-icon-button is-active" : "header-icon-button"}
          onClick={() => onNavigate("settings")}
          aria-label="Open settings"
          title="Settings"
        >
          <GearSix size={18} />
        </button>
      </div>
    </header>
  );
}
