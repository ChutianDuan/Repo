import type { Icon } from "@phosphor-icons/react";
import {
  Brain,
  BracketsCurly,
  ChatCircleText,
  Cpu,
  Database,
  FloppyDisk,
  Funnel,
  GitBranch,
  MagnifyingGlass,
  Rows,
} from "@phosphor-icons/react";
import { useState } from "react";
import type { AgentTraceRow, TraceCitation } from "../AgentTracePanel";
import type { ChatMessage } from "../../types/message";
import type { Session } from "../../types/session";
import type { TaskStatus } from "../../types/task";
import { formatDurationMs, formatNumber, formatScore } from "../../utils/format";

type FlowState = "done" | "active" | "waiting" | "failed";

interface ExecutionFlowProps {
  session: Session | null;
  userMessage: ChatMessage | null;
  assistantMessage: ChatMessage | null;
  chatTask: TaskStatus | null;
  rows: AgentTraceRow[];
}

interface FlowNode {
  id: string;
  label: string;
  detail: string;
  Icon: Icon;
  state: FlowState;
}

function rowSucceeded(row: AgentTraceRow | undefined): boolean {
  return Boolean(row && ["SUCCESS", "DONE"].includes(row.status));
}

function lastMatching<T>(items: T[], predicate: (item: T) => boolean): T | undefined {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (predicate(items[index])) return items[index];
  }
  return undefined;
}

export function ExecutionFlow({ session, userMessage, assistantMessage, chatTask, rows }: ExecutionFlowProps) {
  const [selectedId, setSelectedId] = useState("rerank");
  const toolCall = lastMatching(
    rows,
    (row) => row.type === "tool_call" && row.tool === "knowledge_search",
  );
  const toolResult = lastMatching(
    rows,
    (row) => row.type === "tool_result" && row.tool === "knowledge_search",
  );
  const decision = rows.find((row) => row.type === "agent_step" && row.id.includes("decision"));
  const delta = rows.find((row) => row.type === "delta");
  const final = rows.find((row) => row.type === "final");
  const done = rows.find((row) => row.type === "done");
  const generation = rows.find((row) => row.id.includes("generation"));
  const failed = chatTask?.state === "FAILURE" || chatTask?.state === "FAILED";
  const streamActive = chatTask?.state === "PROCESSING";
  const retrieval = toolResult?.retrieval;

  const state = (complete: boolean, active: boolean): FlowState => {
    if (failed && active) return "failed";
    if (complete) return "done";
    return active ? "active" : "waiting";
  };
  const resultReady = rowSucceeded(toolResult);
  const resultFailed = Boolean(
    toolResult && ["FAILED", "FAILURE", "ERROR", "CANCELLED"].includes(toolResult.status),
  );
  const generationReady = Boolean(generation || delta || final || done);
  const nodes: FlowNode[] = [
      { id: "question", label: "用户问题", detail: "user message", Icon: ChatCircleText, state: state(Boolean(userMessage), streamActive && !userMessage) },
      { id: "memory", label: "会话记忆", detail: "summary + recent", Icon: Brain, state: state(Boolean(decision?.eventId), Boolean(session && userMessage) && !decision?.eventId && streamActive) },
      { id: "intent", label: "意图判断", detail: "agent_step", Icon: GitBranch, state: state(rowSucceeded(decision) || Boolean(toolCall), Boolean(decision) && !rowSucceeded(decision)) },
      {
        id: "search",
        label: "knowledge_search",
        detail: resultFailed ? toolResult?.output || "knowledge_search failed" : "tool_call",
        Icon: MagnifyingGlass,
        state: resultFailed ? "failed" : state(resultReady, Boolean(toolCall) && !toolResult),
      },
      { id: "lancedb", label: "LanceDB 召回", detail: "vector recall", Icon: Database, state: state(resultReady, Boolean(toolCall) && !toolResult) },
      { id: "mysql", label: "MySQL Chunk", detail: "hydrate content", Icon: Rows, state: state(resultReady, false) },
      { id: "rerank", label: "CrossEncoder 重排", detail: "rerank", Icon: Funnel, state: state(resultReady, false) },
      { id: "prompt", label: "Prompt 组装", detail: "context build", Icon: BracketsCurly, state: state(generationReady, resultReady && !generationReady) },
      { id: "llm", label: "LLM 生成", detail: "SSE delta", Icon: Cpu, state: state(Boolean(final || done || assistantMessage?.status === "SUCCESS"), Boolean(delta || generation) && !final) },
      { id: "persist", label: "保存回答与 Citations", detail: "message + citations", Icon: FloppyDisk, state: state(Boolean(done || assistantMessage?.status === "SUCCESS"), Boolean(final) && !done) },
  ];
  if (failed) {
    const failedIndex = nodes.findIndex((node) => node.state === "active" || node.state === "waiting");
    if (failedIndex >= 0) {
      nodes[failedIndex] = {
        ...nodes[failedIndex],
        state: "failed",
        detail: chatTask?.error || "execution failed",
      };
    }
  }

  const selected = nodes.find((node) => node.id === selectedId) || nodes[0];
  const citations: TraceCitation[] = toolResult?.citations?.length
    ? toolResult.citations
    : (assistantMessage?.citations || []).map((citation) => ({
        docId: citation.doc_id,
        chunkId: citation.chunk_id,
        chunkIndex: citation.chunk_index,
        score: citation.score,
        snippet: citation.snippet,
      }));
  const originalRanks = citations
    .slice(0, 4)
    .map((citation) => citation.originalRank ?? citation.lancedbRank ?? "--")
    .join(" → ");
  const reranked = citations
    .slice(0, 4)
    .map((citation, index) => `${index + 1}:${citation.chunkIndex ?? "--"}`)
    .join(" → ");
  const detailRows = selected.id === "rerank"
    ? [
        ["输入候选片段", retrieval?.candidateCount == null ? "waiting for tool_result" : formatNumber(retrieval.candidateCount)],
        ["MySQL hydrated", retrieval?.mysqlHydratedCount == null ? "--" : formatNumber(retrieval.mysqlHydratedCount)],
        ["原始召回顺序", originalRanks || "--"],
        ["重排后顺序", reranked || "--"],
        ["Score 变化", citations[0]?.rerankScore == null ? "--" : `${formatScore(citations[0].lancedbScore ?? Number.NaN)} → ${formatScore(citations[0].rerankScore)}`],
        ["保留引用", citations.length ? `${citations.length} chunks` : "--"],
        ["模型", retrieval?.rerankModel || "default: Qwen3-Reranker-0.6B"],
      ]
    : [
        ["节点", selected.label],
        ["事件依据", selected.detail],
        ["当前状态", selected.state],
        ["event_id", lastMatching(rows, (row) => Boolean(row.eventId))?.eventId || "--"],
        ["耗时", formatDurationMs(lastMatching(rows, (row) => row.latencyMs != null)?.latencyMs ?? null)],
      ];

  return (
    <section className="execution-flow" aria-labelledby="execution-flow-title">
      <header className="execution-flow__head">
        <div>
          <h1 id="execution-flow-title">Execution Flow</h1>
          <p>一次 Agent 问答从用户输入到 citations 落库的可观察路径。</p>
        </div>
        <span className={streamActive ? "sse-state is-live" : "sse-state"}>
          SSE {streamActive ? "streaming" : done ? "done" : "idle"}
        </span>
      </header>

      <div className="execution-flow__map">
        <svg className="execution-flow__path" viewBox="0 0 1000 112" preserveAspectRatio="none" aria-hidden="true">
          <path d="M48 55 C145 30 210 78 310 55 S475 32 570 55 S742 76 952 55" />
          {streamActive ? (
            <circle r="4" className="flow-packet">
              <animateMotion dur="3.2s" repeatCount="indefinite" path="M48 55 C145 30 210 78 310 55 S475 32 570 55 S742 76 952 55" />
            </circle>
          ) : null}
        </svg>
        <div className="execution-flow__nodes">
          {nodes.map((node) => (
            <button
              type="button"
              key={node.id}
              className={`execution-node execution-node--${node.state}${selected.id === node.id ? " is-selected" : ""}`}
              onClick={() => setSelectedId(node.id)}
              aria-pressed={selected.id === node.id}
            >
              <span className="execution-node__icon"><node.Icon size={17} /></span>
              <strong>{node.label}</strong>
              <small>{node.detail}</small>
            </button>
          ))}
        </div>
      </div>

      <div className="execution-detail">
        <div className="execution-detail__title">
          <selected.Icon size={18} />
          <div>
            <strong>{selected.label}</strong>
            <span>{selected.state}</span>
          </div>
        </div>
        <dl>
          {detailRows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
