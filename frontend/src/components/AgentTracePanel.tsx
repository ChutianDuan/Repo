import { EmptyState } from "./common/EmptyState";
import { StatusBadge } from "./common/StatusBadge";
import { formatNumber, formatScore, stateTone } from "../utils/format";

export interface TraceCitation {
  docId?: number | null;
  chunkId?: number | null;
  chunkIndex?: number | null;
  score?: number | null;
  snippet?: string;
  title?: string;
}

export interface RetrievalTraceDetails {
  provider?: string;
  denseTopK?: number | null;
  rerankTopK?: number | null;
  candidateCount?: number | null;
  vectorSearchLatencyMs?: number | null;
  rerankLatencyMs?: number | null;
  retrievalLatencyMs?: number | null;
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
}

interface AgentTracePanelProps {
  rows: AgentTraceRow[];
}

function formatLatency(value: number | undefined): string {
  if (value === undefined || value === null) {
    return "--";
  }
  if (value < 1000) {
    return `${value} ms`;
  }
  return `${(value / 1000).toFixed(1)} s`;
}

function metricValue(value: number | null | undefined): string {
  return value === null || value === undefined ? "--" : formatNumber(value);
}

function displayText(value: string | undefined): string {
  return value && value.trim() ? value : "--";
}

function traceKind(row: AgentTraceRow): string {
  if (row.type === "tool_call") {
    return "Tool Call";
  }
  if (row.type === "tool_result") {
    return "Tool Result";
  }
  if (row.id.includes("generation")) {
    return "Final Answer";
  }
  return "Agent Step";
}

function traceTitle(row: AgentTraceRow): string {
  if (row.type === "tool_call") {
    return row.tool ? `调用 ${row.tool}` : "调用工具";
  }
  if (row.type === "tool_result") {
    return row.tool ? `${row.tool} 返回结果` : "工具返回结果";
  }
  return displayText(row.output || row.type);
}

export function AgentTracePanel({ rows }: AgentTracePanelProps) {
  const latestStatus = rows[rows.length - 1]?.status || "idle";
  const toolCallCount = rows.filter((row) => row.type === "tool_call").length;
  const agentStepCount = rows.filter((row) => row.type !== "tool_call" && row.type !== "tool_result").length;
  const totalLatency = rows.reduce((sum, row) => sum + (row.latencyMs || 0), 0);

  return (
    <aside className="agent-trace-panel">
      <div className="agent-trace-panel__head">
        <div>
          <span className="section-label">Agent Trace</span>
          <h2>执行路径</h2>
        </div>
        <StatusBadge label={latestStatus} tone={stateTone(latestStatus)} />
      </div>

      <section className="agent-trace-section">
        <div className="trace-metrics" aria-label="agent trace metrics">
          <div>
            <span>Agent Steps</span>
            <strong>{formatNumber(agentStepCount)}</strong>
          </div>
          <div>
            <span>Tool Calls</span>
            <strong>{formatNumber(toolCallCount)}</strong>
          </div>
          <div>
            <span>Latency</span>
            <strong>{formatLatency(totalLatency || undefined)}</strong>
          </div>
        </div>

        {rows.length === 0 ? (
          <EmptyState title="暂无 Agent 轨迹" description="提问后展示判断、工具调用、检索结果和生成步骤。" />
        ) : (
          <div className="agent-path" aria-label="Agent execution path">
            {rows.map((row) => (
              <article key={row.id} className={`agent-path-card agent-path-card--${stateTone(row.status)}`}>
                <div className="agent-path-card__marker">{row.step}</div>
                <div className="agent-path-card__body">
                  <div className="agent-path-card__top">
                    <span>{traceKind(row)}</span>
                    <StatusBadge label={row.status} tone={stateTone(row.status)} />
                  </div>
                  <h3>{traceTitle(row)}</h3>
                  <dl className="agent-path-card__meta">
                    <div>
                      <dt>Type</dt>
                      <dd>{displayText(row.type)}</dd>
                    </div>
                    <div>
                      <dt>Tool</dt>
                      <dd>{displayText(row.tool)}</dd>
                    </div>
                    <div>
                      <dt>Latency</dt>
                      <dd>{formatLatency(row.latencyMs)}</dd>
                    </div>
                  </dl>
                  {row.retrieval ? (
                    <dl className="agent-path-card__meta">
                      <div>
                        <dt>Provider</dt>
                        <dd>{displayText(row.retrieval.provider)}</dd>
                      </div>
                      <div>
                        <dt>Dense TopK</dt>
                        <dd>{metricValue(row.retrieval.denseTopK)}</dd>
                      </div>
                      <div>
                        <dt>Rerank TopK</dt>
                        <dd>{metricValue(row.retrieval.rerankTopK)}</dd>
                      </div>
                      <div>
                        <dt>Candidates</dt>
                        <dd>{metricValue(row.retrieval.candidateCount)}</dd>
                      </div>
                      <div>
                        <dt>Vector</dt>
                        <dd>{formatLatency(row.retrieval.vectorSearchLatencyMs ?? undefined)}</dd>
                      </div>
                      <div>
                        <dt>Rerank</dt>
                        <dd>{formatLatency(row.retrieval.rerankLatencyMs ?? undefined)}</dd>
                      </div>
                      <div>
                        <dt>Total</dt>
                        <dd>{formatLatency(row.retrieval.retrievalLatencyMs ?? undefined)}</dd>
                      </div>
                    </dl>
                  ) : null}
                  {row.citations && row.citations.length > 0 ? (
                    <div className="agent-trace-citations">
                      {row.citations.slice(0, 3).map((citation, index) => (
                        <article key={`${row.id}-citation-${citation.chunkId ?? index}`}>
                          <header>
                            <strong>{displayText(citation.title || `doc ${citation.docId ?? "--"}`)}</strong>
                            <span>chunk {metricValue(citation.chunkIndex)} / score {formatScore(citation.score ?? Number.NaN)}</span>
                          </header>
                          <p title={citation.snippet}>{displayText(citation.snippet)}</p>
                        </article>
                      ))}
                    </div>
                  ) : null}
                  <div className="agent-path-card__io">
                    <div>
                      <span>Input</span>
                      <p title={row.input}>{displayText(row.input)}</p>
                    </div>
                    <div>
                      <span>Output</span>
                      <p title={row.output}>{displayText(row.output)}</p>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </aside>
  );
}
