import type { ReactNode } from "react";
import type { ChatMessage } from "../../types/message";
import type { Session } from "../../types/session";
import { StatusBadge } from "../common/StatusBadge";
import { MessageList } from "./MessageList";
import { ChatInputBar } from "./ChatInputBar";
import { stateTone } from "../../utils/format";

interface ChatWorkspaceProps {
  session: Session | null;
  documentLabel: string;
  documentStatus: string;
  messages: ChatMessage[];
  question: string;
  topK: number;
  ragEnabled: boolean;
  pending: string | null;
  canAsk: boolean;
  selectedFileName: string | null;
  error: string | null;
  toolbar?: ReactNode;
  onQuestionChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onRagEnabledChange: (value: boolean) => void;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
  onAsk: () => void;
}

export function ChatWorkspace({
  session,
  documentLabel,
  documentStatus,
  messages,
  question,
  topK,
  ragEnabled,
  pending,
  canAsk,
  selectedFileName,
  error,
  toolbar,
  onQuestionChange,
  onTopKChange,
  onRagEnabledChange,
  onFileChange,
  onUpload,
  onAsk,
}: ChatWorkspaceProps) {
  return (
    <section className="chat-workspace">
      <div className="conversation-header">
        <div>
          <p className="eyebrow">Current Conversation</p>
          <h1>{session?.title || "未创建会话"}</h1>
          <p>{documentLabel}</p>
        </div>
        <div className="conversation-header__actions">
          <StatusBadge label={documentStatus} tone={stateTone(documentStatus)} />
          {toolbar}
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="message-list-shell">
        <MessageList messages={messages} />
      </div>

      <ChatInputBar
        question={question}
        topK={topK}
        ragEnabled={ragEnabled}
        pending={pending}
        canAsk={canAsk}
        selectedFileName={selectedFileName}
        onQuestionChange={onQuestionChange}
        onTopKChange={onTopKChange}
        onRagEnabledChange={onRagEnabledChange}
        onFileChange={onFileChange}
        onUpload={onUpload}
        onAsk={onAsk}
      />
    </section>
  );
}
