import type { MonitorOverview } from "../../types/monitor";
import { formatDateTime, formatNumber } from "../../utils/format";

interface AppFooterStatusProps {
  overview: MonitorOverview;
  retrievalMode: string;
  modelName: string;
}

export function AppFooterStatus({ overview, retrievalMode, modelName }: AppFooterStatusProps) {
  return (
    <footer className="app-footer-status">
      <span>API {overview.latency.api_ms ?? "--"}ms</span>
      <span>Worker {overview.services.worker === "ok" ? "online" : overview.services.worker}</span>
      <span>Docs {overview.rag.documents_ready} ready</span>
      <span>Chunks {overview.rag.total_chunks === null ? "--" : formatNumber(overview.rag.total_chunks)}</span>
      <span>Retrieval {retrievalMode}</span>
      <span>Model {modelName}</span>
      <span>Updated {formatDateTime(overview.updated_at)}</span>
    </footer>
  );
}
