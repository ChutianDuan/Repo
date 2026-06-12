import type { Citation } from "../../types/citation";
import type { TaskStatus } from "../../types/task";
import { EmptyState } from "../common/EmptyState";
import { ProgressBar } from "../common/ProgressBar";
import { StatusBadge } from "../common/StatusBadge";
import { formatDurationMs, formatNumber, formatScore, stateTone } from "../../utils/format";

interface ReferencePanelProps {
  citations: Citation[];
  chatTask: TaskStatus | null;
  ingestTask: TaskStatus | null;
}

function getMetaText(meta: Record<string, unknown> | null | undefined, key: string): string {
  const value = meta?.[key];
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return String(value);
}

function getMetaNumber(meta: Record<string, unknown> | null | undefined, key: string): number | null {
  const value = meta?.[key];
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function ReferencePanel({ citations, chatTask, ingestTask }: ReferencePanelProps) {
  const retrievedCount = getMetaNumber(chatTask?.meta, "retrieved_count");
  const rawHitCount = getMetaNumber(chatTask?.meta, "raw_hit_count");
  const retrievalMs = getMetaNumber(chatTask?.meta, "retrieval_ms");
  const vectorSearchMs = getMetaNumber(chatTask?.meta, "lancedb_ms");
  const rerankMs = getMetaNumber(chatTask?.meta, "rerank_ms");
  const citationCount = citations.length || getMetaNumber(chatTask?.meta, "citation_count") || 0;

  return (
    <aside className="reference-panel">
      <div className="reference-panel__head">
        <div>
          <span className="section-label">Evidence</span>
          <h2>检索证据</h2>
        </div>
        <StatusBadge label={`${formatNumber(citationCount)} sources`} tone={citationCount > 0 ? "ok" : "muted"} />
      </div>

      <section className="reference-section reference-section--metrics">
        <div className="evidence-metrics" aria-label="retrieval evidence metrics">
          <div>
            <span>Retrieval Chunks</span>
            <strong>{formatNumber(retrievedCount)}</strong>
          </div>
          <div>
            <span>Citations</span>
            <strong>{formatNumber(citationCount)}</strong>
          </div>
          <div>
            <span>Latency</span>
            <strong>{formatDurationMs(retrievalMs)}</strong>
          </div>
          <div>
            <span>Vector Search</span>
            <strong>{formatDurationMs(vectorSearchMs)}</strong>
          </div>
          <div>
            <span>Rerank</span>
            <strong>{formatDurationMs(rerankMs)}</strong>
          </div>
          <div>
            <span>Status</span>
            <strong>{chatTask?.state || "idle"}</strong>
          </div>
        </div>
      </section>

      <section className="reference-section">
        <div className="reference-section__title">
          <h3>Citations</h3>
          <span>{formatNumber(citations.length)} shown</span>
        </div>
        {citations.length === 0 ? (
          <EmptyState title="暂无引用" description="回答完成后展示来源文档、chunk、分数和片段。" />
        ) : (
          <div className="source-list">
            {citations.map((citation, index) => (
              <article key={`${citation.chunk_id}-${index}`} className="source-card">
                <header>
                  <div>
                    <strong>doc #{citation.doc_id}</strong>
                    <span>chunk #{citation.chunk_index}</span>
                  </div>
                  <span className="score-pill">score {formatScore(citation.score)}</span>
                </header>
                <p>{citation.snippet}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="reference-section">
        <div className="reference-section__title">
          <h3>Retrieval Chunks</h3>
          <span>{rawHitCount === null ? "raw hits --" : `raw hits ${formatNumber(rawHitCount)}`}</span>
        </div>
        <div className="context-grid">
          <span>retrieved</span>
          <strong>{formatNumber(retrievedCount)}</strong>
          <span>context mode</span>
          <strong>{getMetaText(chatTask?.meta, "context_mode")}</strong>
          <span>answer source</span>
          <strong>{getMetaText(chatTask?.meta, "answer_source")}</strong>
          <span>steps used</span>
          <strong>{getMetaText(chatTask?.meta, "steps_used")}</strong>
        </div>
      </section>

      <section className="reference-section">
        <div className="reference-section__title">
          <h3>Status</h3>
          <span>ingest and answer tasks</span>
        </div>
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
            <span>LLM</span>
            <StatusBadge label={chatTask?.state || "idle"} tone={stateTone(chatTask?.state)} />
          </div>
          <ProgressBar value={chatTask?.progress || 0} />
          <small>{getMetaText(chatTask?.meta, "stage")}</small>
        </div>
      </section>
    </aside>
  );
}
