import type { ReactNode } from "react";
import type { AppRoute } from "../../app/router";
import type { HealthSnapshot } from "../../types/api";
import type { MonitorOverview } from "../../types/monitor";
import { AppFooterStatus } from "./AppFooterStatus";
import { AppHeader } from "./AppHeader";

interface AppShellProps {
  route: AppRoute;
  children: ReactNode;
  overview: MonitorOverview;
  health: HealthSnapshot | null;
  refreshing: boolean;
  modelName: string;
  embeddingModelName: string | null;
  onNavigate: (route: AppRoute) => void;
  onRefresh: () => void;
}

export function AppShell({
  route,
  children,
  overview,
  health,
  refreshing,
  modelName,
  embeddingModelName,
  onNavigate,
  onRefresh,
}: AppShellProps) {
  return (
    <div className="workbench-shell workbench-shell--diagram">
      <a className="skip-link" href="#main-content">Skip to workspace</a>
      <AppHeader
        route={route}
        overview={overview}
        health={health}
        onNavigate={onNavigate}
        onRefresh={onRefresh}
        refreshing={refreshing}
      />
      <main id="main-content" className="app-content app-content--diagram">{children}</main>
      <AppFooterStatus
        overview={overview}
        health={health}
        modelName={modelName}
        embeddingModelName={embeddingModelName}
      />
    </div>
  );
}
