import type { ChatMessage } from "../../types/message";
import type { Session } from "../../types/session";
import type { TaskStatus } from "../../types/task";
import { AgentTracePanel, type AgentTraceRow } from "../../components/AgentTracePanel";
import { ChatWorkspace } from "../../components/workspace/ChatWorkspace";
import { ReferencePanel } from "../../components/workspace/ReferencePanel";
import { StatusBadge } from "../../components/common/StatusBadge";
import { formatDurationMs, formatNumber, stateTone } from "../../utils/format";

interface WorkspacePageProps {
  session: Session | null;
  readyDocumentCount: number;
  messages: ChatMessage[];
  question: string;
  topK: number;
  ragEnabled: boolean;
  streamingEnabled: boolean;
  pending: string | null;
  selectedFileName: string | null;
  error: string | null;
  ingestTask: TaskStatus | null;
  chatTask: TaskStatus | null;
  agentTraceRows: AgentTraceRow[];
  onCreateSession: () => void;
  onRefreshMessages: () => void;
  onQuestionChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onRagEnabledChange: (value: boolean) => void;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
  onAsk: () => void;
}

function latestMessageByRole(messages: ChatMessage[], role: ChatMessage["role"]): ChatMessage | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === role) {
      return messages[index];
    }
  }
  return null;
}

function textPreview(value: string | undefined, fallback: string, maxLength = 180): string {
  const trimmed = value?.trim();
  if (!trimmed) {
    return fallback;
  }
  return trimmed.length > maxLength ? `${trimmed.slice(0, maxLength - 1)}...` : trimmed;
}

function metaNumber(meta: Record<string, unknown> | null | undefined, key: string): number | null {
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

function metaText(meta: Record<string, unknown> | null | undefined, key: string): string | null {
  const value = meta?.[key];
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return String(value);
}

type PipelineState = "done" | "active" | "idle" | "missing";

interface PipelineStep {
  label: string;
  detail: string;
  state: PipelineState;
}

function pipelineStateLabel(state: PipelineState): string {
  if (state === "done") {
    return "done";
  }
  if (state === "active") {
    return "active";
  }
  if (state === "missing") {
    return "not reported";
  }
  return "idle";
}

export function WorkspacePage({
  session,
  readyDocumentCount,
  messages,
  question,
  topK,
  ragEnabled,
  streamingEnabled,
  pending,
  selectedFileName,
  error,
  ingestTask,
  chatTask,
  agentTraceRows,
  onCreateSession,
  onRefreshMessages,
  onQuestionChange,
  onTopKChange,
  onRagEnabledChange,
  onFileChange,
  onUpload,
  onAsk,
}: WorkspacePageProps) {
  const assistantMessage = latestMessageByRole(messages, "assistant");
  const userMessage = latestMessageByRole(messages, "user");
  const documentLabel = `${readyDocumentCount} 份文档可检索`;
  const documentStatus = readyDocumentCount > 0 ? "indexed" : "EMPTY";
  const canAsk = Boolean(session);
  const latestStatus = agentTraceRows[agentTraceRows.length - 1]?.status || chatTask?.state || "idle";
  const latestQuestion = textPreview(userMessage?.content || question, "等待提问");
  const finalAnswer = textPreview(assistantMessage?.content, "等待回答", 220);
  const retrievedCount = metaNumber(chatTask?.meta, "retrieved_count");
  const rawHitCount = metaNumber(chatTask?.meta, "raw_hit_count");
  const retrievalMs = metaNumber(chatTask?.meta, "retrieval_ms") ?? metaNumber(assistantMessage?.meta, "retrieval_ms");
  const e2eLatencyMs = metaNumber(chatTask?.meta, "e2e_latency_ms") ?? metaNumber(assistantMessage?.meta, "e2e_latency_ms");
  const citationCount = assistantMessage?.citations.length ?? metaNumber(chatTask?.meta, "citation_count") ?? 0;
  const hasReadyDocuments = readyDocumentCount > 0;
  const ingestActive = pending === "upload" || ingestTask?.state === "PENDING" || ingestTask?.state === "PROCESSING";
  const chatActive = pending === "chat" || chatTask?.state === "PROCESSING";
  const chatDone = chatTask?.state === "SUCCESS" || assistantMessage?.status === "SUCCESS";
  const rerankDetail = metaText(chatTask?.meta, "rerank_count") || metaText(chatTask?.meta, "rerank_ms");
  const pipelineSteps: PipelineStep[] = [
    {
      label: "Upload",
      detail: hasReadyDocuments ? `${formatNumber(readyDocumentCount)} ready docs` : "waiting for docs",
      state: hasReadyDocuments ? "done" : ingestActive ? "active" : "idle",
    },
    {
      label: "Chunk",
      detail: metaText(ingestTask?.meta, "stage") || (hasReadyDocuments ? "chunks indexed" : "not started"),
      state: hasReadyDocuments ? "done" : ingestActive ? "active" : "idle",
    },
    {
      label: "Embedding",
      detail: hasReadyDocuments ? "vectors ready" : "waiting for chunks",
      state: hasReadyDocuments ? "done" : ingestActive ? "active" : "idle",
    },
    {
      label: "LanceDB",
      detail: hasReadyDocuments ? "index ready" : "waiting for vectors",
      state: hasReadyDocuments ? "done" : ingestActive ? "active" : "idle",
    },
    {
      label: "Retrieval",
      detail: retrievedCount === null ? `topK ${topK}` : `${formatNumber(retrievedCount)} chunks`,
      state: retrievedCount !== null || rawHitCount !== null ? "done" : chatActive ? "active" : "idle",
    },
    {
      label: "Rerank",
      detail: rerankDetail || "not reported by API",
      state: rerankDetail ? "done" : chatActive || chatDone ? "missing" : "idle",
    },
    {
      label: "LLM",
      detail: metaText(chatTask?.meta, "answer_source") || (ragEnabled ? "agent answer" : "direct answer"),
      state: chatDone ? "done" : chatActive ? "active" : "idle",
    },
    {
      label: "Citations",
      detail: `${formatNumber(citationCount)} sources`,
      state: citationCount > 0 ? "done" : chatActive ? "active" : "idle",
    },
  ];

  return (
    <div className="workspace-page">
      <section className="rag-workbench-board">
        <div className="rag-workbench-board__head">
          <div>
            <span className="section-label">RAG Workbench</span>
            <h1>问答执行台</h1>
            <p>把一次问答拆成可解释的检索、工具调用、生成和引用链路。</p>
          </div>
          <div className="rag-workbench-board__status">
            <StatusBadge label={latestStatus} tone={stateTone(latestStatus)} />
            <span>{ragEnabled ? `RAG top_${topK}` : "Direct"}</span>
          </div>
        </div>

        <div className="rag-focus-grid">
          <article className="rag-focus-card rag-focus-card--question">
            <span>User Question</span>
            <strong>{latestQuestion}</strong>
          </article>
          <article className="rag-focus-card rag-focus-card--answer">
            <span>Final Answer</span>
            <strong>{finalAnswer}</strong>
          </article>
          <article className="rag-focus-card">
            <span>Agent Steps</span>
            <strong>{formatNumber(agentTraceRows.length)}</strong>
          </article>
          <article className="rag-focus-card">
            <span>Latency</span>
            <strong>{formatDurationMs(e2eLatencyMs ?? retrievalMs)}</strong>
          </article>
        </div>

        <div className="rag-pipeline-rail" aria-label="RAG pipeline">
          {pipelineSteps.map((step) => (
            <article key={step.label} className={`rag-pipeline-step rag-pipeline-step--${step.state}`}>
              <span>{step.label}</span>
              <strong>{pipelineStateLabel(step.state)}</strong>
              <small>{step.detail}</small>
            </article>
          ))}
        </div>
      </section>

      <div className="workspace-main-grid">
        <ChatWorkspace
          session={session}
          documentLabel={documentLabel}
          documentStatus={documentStatus}
          messages={messages}
          question={question}
          topK={topK}
          ragEnabled={ragEnabled}
          streamingEnabled={streamingEnabled}
          pending={pending}
          canAsk={canAsk}
          selectedFileName={selectedFileName}
          error={error}
          toolbar={
            <>
              <button type="button" className="button-secondary" onClick={onCreateSession} disabled={pending !== null}>
                {pending === "session" ? "创建中" : session ? "新会话" : "创建会话"}
              </button>
              <button type="button" className="button-ghost" onClick={onRefreshMessages} disabled={pending !== null || !session}>
                刷新
              </button>
            </>
          }
          onQuestionChange={onQuestionChange}
          onTopKChange={onTopKChange}
          onRagEnabledChange={onRagEnabledChange}
          onFileChange={onFileChange}
          onUpload={onUpload}
          onAsk={onAsk}
        />
        <div className="workspace-side-panel">
          <AgentTracePanel rows={agentTraceRows} />
          <ReferencePanel
            citations={assistantMessage?.citations || []}
            chatTask={chatTask}
            ingestTask={ingestTask}
          />
        </div>
      </div>
    </div>
  );
}
