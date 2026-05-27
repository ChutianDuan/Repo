import { EmptyState } from "./common/EmptyState";
import { StatusBadge } from "./common/StatusBadge";
import { stateTone } from "../utils/format";

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

function displayText(value: string | undefined): string {
  return value && value.trim() ? value : "--";
}

export function AgentTracePanel({ rows }: AgentTracePanelProps) {
  const latestStatus = rows[rows.length - 1]?.status || "idle";

  return (
    <aside className="agent-trace-panel">
      <div className="agent-trace-panel__head">
        <div>
          <p className="eyebrow">Agent Trace</p>
          <h2>执行轨迹</h2>
        </div>
        <StatusBadge label={latestStatus} tone={stateTone(latestStatus)} />
      </div>

      <section className="agent-trace-section">
        {rows.length === 0 ? (
          <EmptyState title="暂无 Agent 轨迹" description="Agent 开始判断、检索和生成后会实时展示步骤。" />
        ) : (
          <>
            <div className="agent-trace-timeline">
              {rows.map((row) => (
                <div key={`${row.id}-summary`}>
                  <strong>Step {row.step}</strong>
                  <span>{displayText(row.output || row.type)}</span>
                </div>
              ))}
            </div>

            <div className="agent-trace-table" role="table" aria-label="Agent trace">
              <div className="agent-trace-table__row agent-trace-table__row--head" role="row">
                <span>Step</span>
                <span>Type</span>
                <span>Tool</span>
                <span>Input</span>
                <span>Output</span>
                <span>Latency</span>
                <span>Status</span>
              </div>
              {rows.map((row) => (
                <div key={row.id} className="agent-trace-table__row" role="row">
                  <span>{row.step}</span>
                  <span>{displayText(row.type)}</span>
                  <span>{displayText(row.tool)}</span>
                  <span title={row.input}>{displayText(row.input)}</span>
                  <span title={row.output}>{displayText(row.output)}</span>
                  <span>{formatLatency(row.latencyMs)}</span>
                  <span>
                    <StatusBadge label={row.status} tone={stateTone(row.status)} />
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </aside>
  );
}

