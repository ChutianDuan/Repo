import { CaretRight } from "@phosphor-icons/react";
import type { HealthSnapshot } from "../../types/api";
import type { MonitorOverview, ServiceState } from "../../types/monitor";

interface AppFooterStatusProps {
  overview: MonitorOverview;
  health: HealthSnapshot | null;
  modelName: string;
  embeddingModelName: string | null;
}

interface RuntimeLink {
  label: string;
  detail?: string;
  state: ServiceState;
}

function healthState(value: boolean | undefined): ServiceState {
  if (value === true) return "ok";
  if (value === false) return "error";
  return "unknown";
}

export function AppFooterStatus({ overview, health, modelName, embeddingModelName }: AppFooterStatusProps) {
  const services: RuntimeLink[] = [
    { label: "Drogon Gateway", state: health ? "ok" : "unknown" },
    { label: "FastAPI", state: healthState(health?.python?.ok) },
    { label: "Celery Worker", state: overview.services.worker },
    { label: "MySQL", state: overview.services.mysql },
    { label: "Redis", state: overview.services.redis },
    {
      label: "LanceDB",
      detail: overview.rag.documents_ready > 0 ? "indexed" : "no indexed docs",
      state: overview.rag.documents_ready > 0 ? "ok" : "unknown",
    },
    {
      label: "Embedding",
      detail: embeddingModelName || "default: Qwen3-Embedding-0.6B",
      state: overview.services.embedding,
    },
    { label: "LLM", detail: modelName, state: overview.services.llm },
  ];

  return (
    <footer className="app-footer-status app-footer-status--runtime" aria-label="Runtime dependency chain">
      {services.map((service, index) => (
        <span className="runtime-link-wrap" key={service.label}>
          <span className={`runtime-link runtime-link--${service.state}`} title={`${service.label}: ${service.state}`}>
            <span className="runtime-link__state" aria-hidden="true" />
            <strong>{service.label}</strong>
            {service.detail ? <small>{service.detail}</small> : null}
          </span>
          {index < services.length - 1 ? <CaretRight size={12} aria-hidden="true" /> : null}
        </span>
      ))}
    </footer>
  );
}
