import type { Citation } from "../../types/citation";
import type { TaskStatus } from "../../types/task";
import { EmptyState } from "../common/EmptyState";
import { ProgressBar } from "../common/ProgressBar";
import { StatusBadge } from "../common/StatusBadge";
import { formatScore, stateTone } from "../../utils/format";

interface ReferencePanelProps {
  citations: Citation[];
  chatTask: TaskStatus | null;
  ingestTask: TaskStatus | null;
}

function getMetaText(meta: Record<string, unknown> | null | undefined, key: string): string {
  const value = meta?.[key];
  if (value === null || value === undefined) {
    return "--";
  }
  return String(value);
}

export function ReferencePanel({ citations, chatTask, ingestTask }: ReferencePanelProps) {
  return (
    <aside className="reference-panel">
      <div className="reference-panel__head">
        <div>
          <p className="eyebrow">Evidence</p>
          <h2>引用与检索命中</h2>
        </div>
        <StatusBadge label={`${citations.length} sources`} tone={citations.length > 0 ? "ok" : "muted"} />
      </div>

      <section className="reference-section">
        <h3>Answer Sources</h3>
        {citations.length === 0 ? (
          <EmptyState title="暂无引用" description="回答完成后，这里会展示 chunk 分数、片段和来源文档。" />
        ) : (
          <div className="source-list">
            {citations.map((citation, index) => (
              <article key={`${citation.chunk_id}-${index}`} className="source-card">
                <div>
                  <strong>doc #{citation.doc_id}</strong>
                  <span>chunk #{citation.chunk_index}</span>
                </div>
                <span className="score-pill">{formatScore(citation.score)}</span>
                <p>{citation.snippet}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="reference-section">
        <h3>Retrieved Chunks</h3>
        <div className="context-grid">
          <span>retrieved</span>
          <strong>{getMetaText(chatTask?.meta, "retrieved_count")}</strong>
          <span>raw hits</span>
          <strong>{getMetaText(chatTask?.meta, "raw_hit_count")}</strong>
          <span>context mode</span>
          <strong>{getMetaText(chatTask?.meta, "context_mode")}</strong>
          <span>source</span>
          <strong>{getMetaText(chatTask?.meta, "answer_source")}</strong>
        </div>
      </section>

      <section className="reference-section">
        <h3>Pipeline</h3>
        <div className="pipeline-card">
          <div>
            <span>Ingest</span>
            <StatusBadge label={ingestTask?.state || "idle"} tone={stateTone(ingestTask?.state)} />
          </div>
          <ProgressBar value={ingestTask?.progress || 0} />
          <small>{getMetaText(ingestTask?.meta, "stage")}</small>
        </div>
        <div className="pipeline-card">
          <div>
            <span>Chat</span>
            <StatusBadge label={chatTask?.state || "idle"} tone={stateTone(chatTask?.state)} />
          </div>
          <ProgressBar value={chatTask?.progress || 0} />
          <small>{getMetaText(chatTask?.meta, "stage")}</small>
        </div>
      </section>
    </aside>
  );
}
