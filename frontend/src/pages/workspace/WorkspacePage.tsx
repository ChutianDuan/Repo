import type { ChatMessage } from "../../types/message";
import type { Session } from "../../types/session";
import type { TaskStatus } from "../../types/task";
import { ChatWorkspace } from "../../components/workspace/ChatWorkspace";
import { ReferencePanel } from "../../components/workspace/ReferencePanel";

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
  onCreateSession: () => void;
  onRefreshMessages: () => void;
  onQuestionChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onRagEnabledChange: (value: boolean) => void;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
  onAsk: () => void;
}

function latestAssistantMessage(messages: ChatMessage[]): ChatMessage | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === "assistant") {
      return messages[index];
    }
  }
  return null;
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
  onCreateSession,
  onRefreshMessages,
  onQuestionChange,
  onTopKChange,
  onRagEnabledChange,
  onFileChange,
  onUpload,
  onAsk,
}: WorkspacePageProps) {
  const assistantMessage = latestAssistantMessage(messages);
  const documentLabel = `Global KB · ${readyDocumentCount} ready docs`;
  const documentStatus = readyDocumentCount > 0 ? "READY" : "EMPTY";
  const canAsk = Boolean(session);

  return (
    <div className="workspace-page">
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
              {pending === "session" ? "Creating" : session ? "New Session" : "Create Session"}
            </button>
            <button type="button" className="button-ghost" onClick={onRefreshMessages} disabled={pending !== null || !session}>
              Refresh
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
      <ReferencePanel
        citations={assistantMessage?.citations || []}
        chatTask={chatTask}
        ingestTask={ingestTask}
      />
    </div>
  );
}
