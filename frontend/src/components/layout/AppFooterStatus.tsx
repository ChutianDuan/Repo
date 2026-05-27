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
      <span>文档 {formatNumber(overview.rag.documents_ready)} ready</span>
      <span>Chunks {overview.rag.total_chunks === null ? "--" : formatNumber(overview.rag.total_chunks)}</span>
      <span>检索 {retrievalMode}</span>
      <span>模型 {modelName}</span>
      <span>Worker {overview.services.worker === "ok" ? "online" : overview.services.worker}</span>
      <span>更新 {formatDateTime(overview.updated_at)}</span>
    </footer>
  );
}
