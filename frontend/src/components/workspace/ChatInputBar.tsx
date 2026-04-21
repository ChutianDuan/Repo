import type { ChangeEvent, FormEvent } from "react";

interface ChatInputBarProps {
  question: string;
  topK: number;
  ragEnabled: boolean;
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
        placeholder="询问这份文档中的事实、结论或依据..."
        rows={4}
      />
      <div className="chat-input-bar__controls">
        <label className="file-control">
          <input type="file" accept=".md,.txt,.json,.csv,.pdf,.docx" onChange={handleFileChange} />
          <span>{selectedFileName || "Attach document"}</span>
        </label>
        <button type="button" className="button-secondary" onClick={onUpload} disabled={pending !== null}>
          {pending === "upload" ? "Indexing" : "Upload"}
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
          {pending === "chat" ? "Running" : "Send"}
        </button>
      </div>
    </form>
  );
}
