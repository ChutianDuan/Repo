import type { MonitorOverview, ServiceState } from "../../types/monitor";
import { HealthDot } from "../common/HealthDot";

interface ServiceHealthPanelProps {
  overview: MonitorOverview;
}

const SERVICE_LABELS: Array<[keyof MonitorOverview["services"], string]> = [
  ["mysql", "MySQL"],
  ["redis", "Redis"],
  ["worker", "Celery Worker"],
  ["embedding", "Embedding Service"],
  ["llm", "LLM Service"],
  ["api", "API"],
];

function statusText(state: ServiceState): string {
  if (state === "ok") {
    return "healthy";
  }
  if (state === "error") {
    return "down";
  }
  if (state === "warn") {
    return "degraded";
  }
  return "unknown";
}

export function ServiceHealthPanel({ overview }: ServiceHealthPanelProps) {
  return (
    <div className="service-health-panel">
      {SERVICE_LABELS.map(([key, label]) => (
        <article key={key} className="service-health-item">
          <HealthDot label={label} state={overview.services[key]} />
          <strong>{statusText(overview.services[key])}</strong>
        </article>
      ))}
    </div>
  );
}
