import {
  ArrowCounterClockwise,
  Broadcast,
  Check,
  WarningCircle,
} from "@phosphor-icons/react";
import { formatDurationMs, formatScore } from "../utils/format";

export interface TraceCitation {
  docId?: number | null;
  chunkId?: number | null;
  chunkIndex?: number | null;
  score?: number | null;
  snippet?: string;
  title?: string;
  originalRank?: number | null;
  lancedbRank?: number | null;
  lancedbScore?: number | null;
  rerankScore?: number | null;
}

export interface RetrievalTraceDetails {
  provider?: string;
  denseTopK?: number | null;
  rerankTopK?: number | null;
  candidateCount?: number | null;
  mysqlHydratedCount?: number | null;
  vectorSearchLatencyMs?: number | null;
  rerankLatencyMs?: number | null;
  retrievalLatencyMs?: number | null;
  rerankModel?: string;
  rerankProvider?: string;
  rerankUsed?: boolean | null;
}

export interface AgentTraceRow {
  id: string;
  step: number;
  type: string;
  tool?: string;
  input?: string;
  output?: string;
  latencyMs?: number;
  status: string;
  startedAtMs?: number;
  retrieval?: RetrievalTraceDetails;
  citations?: TraceCitation[];
  runId?: number | null;
  stepId?: number | null;
  eventId?: string | null;
  lastEventId?: string | null;
  resumeAttempt?: number;
}

interface AgentTracePanelProps {
  rows: AgentTraceRow[];
}

function lastEventId(rows: AgentTraceRow[]): string | null {
  for (let index = rows.length - 1; index >= 0; index -= 1) {
    if (rows[index].eventId) return rows[index].eventId || null;
  }
  return null;
}

function eventTitle(row: AgentTraceRow): string {
  if (row.type === "resume") return `Resumed from event ${row.lastEventId || "unknown"}`;
  if (row.type === "tool_call") return row.tool || "tool call";
  if (row.type === "tool_result") return `${row.tool || "tool"} result`;
  if (row.type === "delta") return "answer tokens";
  if (row.type === "final") return "answer and citations persisted";
  if (row.type === "done") return "stream completed";
  return row.output || row.type;
}

function isFailed(row: AgentTraceRow): boolean {
  return ["FAILED", "FAILURE", "ERROR"].includes(row.status);
}

export function AgentTracePanel({ rows }: AgentTracePanelProps) {
  const currentLastEventId = lastEventId(rows);
  const currentRunId = rows.find((row) => row.runId)?.runId;

  return (
    <aside className="agent-trace-panel agent-trace-timeline" aria-labelledby="agent-trace-title">
      <header className="agent-trace-timeline__head">
        <div>
          <span><Broadcast size={15} /> SSE transport</span>
          <h2 id="agent-trace-title">Agent Trace</h2>
        </div>
        <dl>
          <div><dt>run_id</dt><dd>{currentRunId ?? "--"}</dd></div>
          <div><dt>Last-Event-ID</dt><dd>{currentLastEventId ?? "--"}</dd></div>
        </dl>
      </header>

      {rows.length === 0 ? (
        <div className="agent-trace-timeline__empty">
          <p>等待 Agent SSE 事件。</p>
          <code>agent_step → tool_call → tool_result → delta → final → done</code>
        </div>
      ) : (
        <ol className="trace-event-list">
          {rows.map((row) => {
            const failed = isFailed(row);
            const resumed = row.type === "resume";
            return (
              <li
                key={row.id}
                className={`trace-event trace-event--${row.type}${resumed ? " is-resume" : ""}${failed ? " is-failed" : ""}`}
              >
                <span className="trace-event__marker" aria-hidden="true">
                  {resumed ? <ArrowCounterClockwise size={13} /> : failed ? <WarningCircle size={13} /> : <Check size={12} />}
                </span>
                <div className="trace-event__content">
                  <div className="trace-event__topline">
                    <code>{row.type}</code>
                    <span>{row.status.toLowerCase()}</span>
                  </div>
                  <strong>{eventTitle(row)}</strong>
                  <dl>
                    <div><dt>event_id</dt><dd>{row.eventId || "--"}</dd></div>
                    <div><dt>step_id</dt><dd>{row.stepId ?? "--"}</dd></div>
                    <div><dt>tool_name</dt><dd>{row.tool || "--"}</dd></div>
                    <div><dt>latency</dt><dd>{formatDurationMs(row.latencyMs ?? null)}</dd></div>
                  </dl>
                  {row.retrieval ? (
                    <div className="trace-event__retrieval">
                      <span>{row.retrieval.provider || "retrieval"}</span>
                      <span>{row.retrieval.candidateCount ?? "--"} candidates</span>
                      <span>{row.retrieval.rerankModel || "reranker unknown"}</span>
                    </div>
                  ) : null}
                  {row.citations?.length ? (
                    <div className="trace-event__evidence">
                      {row.citations.slice(0, 2).map((citation, index) => (
                        <span key={`${row.id}-${citation.chunkId ?? index}`}>
                          chunk {citation.chunkIndex ?? "--"} / {formatScore(citation.rerankScore ?? citation.score ?? Number.NaN)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </aside>
  );
}
