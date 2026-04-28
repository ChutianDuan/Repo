import type { ChangeEvent, FormEvent } from "react";

interface ChatInputBarProps {
  question: string;
  topK: number;
  ragEnabled: boolean;
  streamingEnabled: boolean;
  pending: string | null;
  canAsk: boolean;
  selectedFileName: string | null;
  onQuestionChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onRagEnabledChange: (value: boolean) => void;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
  onAsk: () => void;
}

export function ChatInputBar({
  question,
  topK,
  ragEnabled,
  streamingEnabled,
  pending,
  canAsk,
  selectedFileName,
  onQuestionChange,
  onTopKChange,
  onRagEnabledChange,
  onFileChange,
  onUpload,
  onAsk,
}: ChatInputBarProps) {
  const isChatting = pending === "chat";

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onAsk();
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.target.files?.[0] ?? null);
  }

  return (
    <form className="chat-input-bar" onSubmit={handleSubmit}>
      <textarea
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder={isChatting ? "正在接收回答..." : "输入问题..."}
        rows={3}
        disabled={isChatting}
      />
      <div className="chat-input-bar__controls">
        <label className="file-control">
          <input type="file" accept=".md,.txt,.json,.csv,.pdf,.docx" onChange={handleFileChange} />
          <span>{selectedFileName || "选择文档"}</span>
        </label>
        <button type="button" className="button-secondary" onClick={onUpload} disabled={pending !== null}>
          {pending === "upload" ? "索引中" : "上传"}
        </button>
        <label className="toggle-control">
          <input
            type="checkbox"
            checked={ragEnabled}
            onChange={(event) => onRagEnabledChange(event.target.checked)}
          />
          <span>RAG {ragEnabled ? "ON" : "OFF"}</span>
        </label>
        <label className="mini-field">
          <span>top_k</span>
          <input
            type="number"
            min={1}
            max={20}
            value={topK}
            onChange={(event) => onTopKChange(Number(event.target.value))}
          />
        </label>
        <button type="submit" disabled={pending !== null || !canAsk || !question.trim()}>
          {isChatting ? (streamingEnabled ? "Streaming" : "Running") : "Send"}
        </button>
      </div>
    </form>
  );
}
