import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { AgentTraceRow } from "../../components/AgentTracePanel";
import { AgentTracePanel } from "../../components/AgentTracePanel";
import { AnswerDocument } from "../../components/workspace/AnswerDocument";
import { ExecutionFlow } from "../../components/workspace/ExecutionFlow";
import { WorkspaceDocumentRail } from "../../components/workspace/WorkspaceDocumentRail";
import type { Citation } from "../../types/citation";
import type { DocumentListItem } from "../../types/document";
import type { ChatMessage } from "../../types/message";
import type { Session, SessionSummary } from "../../types/session";
import type { TaskRecord, TaskStatus } from "../../types/task";

interface WorkspacePageProps {
  session: Session | null;
  sessions: SessionSummary[];
  documents: DocumentListItem[];
  tasks: TaskRecord[];
  selectedDocId: number | null;
  messages: ChatMessage[];
  question: string;
  topK: number;
  ragEnabled: boolean;
  streamingEnabled: boolean;
  pending: string | null;
  selectedFileName: string | null;
  webUrl: string;
  error: string | null;
  chatTask: TaskStatus | null;
  agentTraceRows: AgentTraceRow[];
  onCreateSession: () => void;
  onSelectSession: (sessionId: number) => void;
  onRefreshMessages: () => void;
  onSelectDocument: (docId: number) => void;
  onQuestionChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onRagEnabledChange: (value: boolean) => void;
  onFileChange: (file: File | null) => void;
  onWebUrlChange: (value: string) => void;
  onUpload: () => void;
  onUploadWebDocument: () => void;
  onAsk: () => void;
}

function latestMessageByRole(messages: ChatMessage[], role: ChatMessage["role"]): ChatMessage | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === role) return messages[index];
  }
  return null;
}

export function WorkspacePage({
  session,
  sessions,
  documents,
  tasks,
  selectedDocId,
  messages,
  question,
  topK,
  ragEnabled,
  streamingEnabled,
  pending,
  selectedFileName,
  webUrl,
  error,
  chatTask,
  agentTraceRows,
  onCreateSession,
  onSelectSession,
  onRefreshMessages,
  onSelectDocument,
  onQuestionChange,
  onTopKChange,
  onRagEnabledChange,
  onFileChange,
  onWebUrlChange,
  onUpload,
  onUploadWebDocument,
  onAsk,
}: WorkspacePageProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [hoveredCitation, setHoveredCitation] = useState<Citation | null>(null);
  const [connectorPath, setConnectorPath] = useState<string | null>(null);
  const userMessage = latestMessageByRole(messages, "user");
  const assistantMessage = latestMessageByRole(messages, "assistant");
  const documentNames = useMemo(
    () => new Map(documents.map((document) => [document.doc_id, document.filename])),
    [documents],
  );

  useLayoutEffect(() => {
    function updateConnector() {
      const root = rootRef.current;
      if (!root || !hoveredCitation) {
        setConnectorPath(null);
        return;
      }
      const source = root.querySelector<HTMLElement>(
        `.citation-marker[data-citation-doc-id="${hoveredCitation.doc_id}"]:hover, .citation-marker[data-citation-doc-id="${hoveredCitation.doc_id}"]:focus`,
      ) || root.querySelector<HTMLElement>(`.citation-marker[data-citation-doc-id="${hoveredCitation.doc_id}"]`);
      const target = root.querySelector<HTMLElement>(`[data-doc-id="${hoveredCitation.doc_id}"]`);
      if (!source || !target) {
        setConnectorPath(null);
        return;
      }
      const rootRect = root.getBoundingClientRect();
      const sourceRect = source.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      const startX = sourceRect.left - rootRect.left;
      const startY = sourceRect.top + sourceRect.height / 2 - rootRect.top;
      const endX = targetRect.right - rootRect.left;
      const endY = targetRect.top + targetRect.height / 2 - rootRect.top;
      const bend = Math.max(48, (startX - endX) * 0.4);
      setConnectorPath(`M ${startX} ${startY} C ${startX - bend} ${startY}, ${endX + bend} ${endY}, ${endX} ${endY}`);
    }

    updateConnector();
    window.addEventListener("resize", updateConnector);
    return () => window.removeEventListener("resize", updateConnector);
  }, [hoveredCitation, messages]);

  return (
    <div className="workspace-page workspace-diagram" ref={rootRef}>
      {connectorPath ? (
        <svg className="evidence-connector" aria-hidden="true">
          <path d={connectorPath} />
        </svg>
      ) : null}

      <WorkspaceDocumentRail
        documents={documents}
        tasks={tasks}
        selectedDocId={selectedDocId}
        selectedFileName={selectedFileName}
        webUrl={webUrl}
        pending={pending}
        onSelectDocument={onSelectDocument}
        onFileChange={onFileChange}
        onWebUrlChange={onWebUrlChange}
        onUpload={onUpload}
        onUploadWebDocument={onUploadWebDocument}
      />

      <div className="workspace-diagram__center">
        <ExecutionFlow
          session={session}
          userMessage={userMessage}
          assistantMessage={assistantMessage}
          chatTask={chatTask}
          rows={agentTraceRows}
        />
        <AnswerDocument
          session={session}
          sessions={sessions}
          userMessage={userMessage}
          assistantMessage={assistantMessage}
          question={question}
          topK={topK}
          ragEnabled={ragEnabled}
          streamingEnabled={streamingEnabled}
          pending={pending}
          error={error}
          documentNames={documentNames}
          hoveredCitation={hoveredCitation}
          onCitationHover={setHoveredCitation}
          onCreateSession={onCreateSession}
          onSelectSession={onSelectSession}
          onRefreshMessages={onRefreshMessages}
          onQuestionChange={onQuestionChange}
          onTopKChange={onTopKChange}
          onRagEnabledChange={onRagEnabledChange}
          onAsk={onAsk}
        />
      </div>

      <AgentTracePanel rows={agentTraceRows} />
    </div>
  );
}
