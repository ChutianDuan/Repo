import { useState, type ChangeEvent } from "react";
import {
  FileArrowUp,
  FileText,
  LinkSimple,
  Plus,
} from "@phosphor-icons/react";
import type { DocumentListItem } from "../../types/document";
import type { TaskRecord } from "../../types/task";
import { formatDateTime } from "../../utils/format";

interface WorkspaceDocumentRailProps {
  documents: DocumentListItem[];
  tasks: TaskRecord[];
  selectedDocId: number | null;
  selectedFileName: string | null;
  webUrl: string;
  pending: string | null;
  onSelectDocument: (docId: number) => void;
  onFileChange: (file: File | null) => void;
  onWebUrlChange: (value: string) => void;
  onUpload: () => void;
  onUploadWebDocument: () => void;
}

const SUGGESTED_DOCUMENTS = ["architecture.md", "api_agent.md", "README.md"];

function stageForDocument(document: DocumentListItem, tasks: TaskRecord[]): string {
  const normalizedStatus = String(document.index_status || document.status || "").toLowerCase();
  if (["failed", "failure"].includes(normalizedStatus) || document.error || document.error_message) return "Failed";
  if (["indexed", "ready"].includes(normalizedStatus)) return "Indexed";

  const task = tasks.find((item) => item.entity_type === "document" && item.entity_id === document.doc_id);
  const stage = String(task?.meta?.stage || normalizedStatus).toLowerCase();
  if (stage.includes("chunk")) return "Chunking";
  if (stage.includes("embed") || stage.includes("index")) return "Embedding";
  if (stage.includes("parse") || stage.includes("document")) return "Parsing";
  return "Parsing";
}

export function WorkspaceDocumentRail({
  documents,
  tasks,
  selectedDocId,
  selectedFileName,
  webUrl,
  pending,
  onSelectDocument,
  onFileChange,
  onWebUrlChange,
  onUpload,
  onUploadWebDocument,
}: WorkspaceDocumentRailProps) {
  const [showWebInput, setShowWebInput] = useState(false);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.target.files?.[0] || null);
  }

  return (
    <aside className="document-rail" aria-label="Document workspace">
      <header className="document-rail__head">
        <div>
          <h2>Documents</h2>
          <span>{documents.length} in knowledge base</span>
        </div>
        <Plus size={16} aria-hidden="true" />
      </header>

      <div className="document-rail__actions">
        <label className="rail-action" title="Choose a document">
          <input
            type="file"
            accept=".md,.txt,.json,.csv,.pdf,.docx,.xlsx"
            onChange={handleFileChange}
          />
          <FileArrowUp size={17} />
          <span>{selectedFileName || "上传文件"}</span>
        </label>
        {selectedFileName ? (
          <button type="button" className="rail-index-action" onClick={onUpload} disabled={pending !== null}>
            {pending === "upload" ? "正在索引" : "开始索引"}
          </button>
        ) : null}
        <button
          type="button"
          className={showWebInput ? "rail-action is-active" : "rail-action"}
          onClick={() => setShowWebInput((value) => !value)}
        >
          <LinkSimple size={17} />
          <span>导入网页</span>
        </button>
      </div>

      {showWebInput ? (
        <div className="document-rail__web-input">
          <input
            value={webUrl}
            onChange={(event) => onWebUrlChange(event.target.value)}
            placeholder="https://example.com/docs"
            aria-label="Web page URL"
          />
          <button type="button" onClick={onUploadWebDocument} disabled={pending !== null || !webUrl.trim()}>
            {pending === "web-upload" ? "导入中" : "导入"}
          </button>
        </div>
      ) : null}

      <div className="document-rail__list">
        {documents.length > 0 ? (
          documents.map((document) => {
            const stage = stageForDocument(document, tasks);
            const selected = document.doc_id === selectedDocId;
            return (
              <button
                type="button"
                key={document.doc_id}
                data-doc-id={document.doc_id}
                className={selected ? "document-rail-item is-selected" : "document-rail-item"}
                onClick={() => onSelectDocument(document.doc_id)}
              >
                <FileText size={16} />
                <span className="document-rail-item__main">
                  <strong title={document.filename}>{document.filename}</strong>
                  <small>{stage}</small>
                </span>
                <time>{formatDateTime(document.updated_at || document.created_at)}</time>
              </button>
            );
          })
        ) : (
          <div className="document-rail__empty">
            <p>知识库当前没有文档。</p>
            <span>建议首批资料</span>
            {SUGGESTED_DOCUMENTS.map((name) => (
              <div key={name}>
                <FileText size={15} />
                <strong>{name}</strong>
                <small>waiting for upload</small>
              </div>
            ))}
          </div>
        )}
      </div>

      <footer className="document-rail__foot">
        <span>Index pipeline</span>
        <code>Parse → Chunk → Embedding → LanceDB</code>
      </footer>
    </aside>
  );
}
