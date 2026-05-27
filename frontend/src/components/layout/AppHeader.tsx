import type { AppRoute } from "../../app/router";
import type { MonitorOverview } from "../../types/monitor";
import { formatNumber } from "../../utils/format";
import { HealthDot } from "../common/HealthDot";

interface AppHeaderProps {
  route: AppRoute;
  overview: MonitorOverview;
  searchScope: string;
  onNavigate: (route: AppRoute) => void;
  onRefresh: () => void;
  refreshing: boolean;
}

const routeLabel: Record<AppRoute, string> = {
  workspace: "问答",
  documents: "文档索引",
  tasks: "任务",
  monitor: "状态",
  settings: "配置",
};

export function AppHeader({ route, overview, searchScope, onNavigate, onRefresh, refreshing }: AppHeaderProps) {
  return (
    <header className="app-header app-header--simple">
      <div className="app-header__brand" onClick={() => onNavigate("workspace")} role="button" tabIndex={0}>
        <span className="brand-mark">R</span>
        <div>
          <strong>RAG 笔记助手</strong>
          <small>{routeLabel[route]} · 上传文档后直接提问</small>
        </div>
      </div>

      <div className="app-header__scope">
        <span>知识库</span>
        <strong>{searchScope}</strong>
      </div>

      <div className="app-header__metrics" aria-label="rag summary">
        <span>Ready {formatNumber(overview.rag.documents_ready)}</span>
        <span>Chunks {overview.rag.total_chunks === null ? "--" : formatNumber(overview.rag.total_chunks)}</span>
        <span>Queue {overview.queue.pending + overview.queue.running}</span>
        <HealthDot label="API" state={overview.services.api} compact />
        <HealthDot label="Worker" state={overview.services.worker} compact />
      </div>

      <div className="app-header__actions">
        <button type="button" className="button-ghost" onClick={() => onNavigate("documents")}>
          管理文档
        </button>
        <button type="button" className="button-secondary" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? "刷新中" : "刷新"}
        </button>
      </div>
    </header>
  );
}
