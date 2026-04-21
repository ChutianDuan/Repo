import type { DocumentListItem } from "../../types/document";
import { EmptyState } from "../common/EmptyState";
import { ProgressBar } from "../common/ProgressBar";
import { StatusBadge } from "../common/StatusBadge";
import { TimestampText } from "../common/TimestampText";
import { formatNumber, stateTone } from "../../utils/format";

interface DocumentTableProps {
  documents: DocumentListItem[];
  selectedDocId: number | null;
  onSelectDocument: (docId: number) => void;
}

export function DocumentTable({ documents, selectedDocId, onSelectDocument }: DocumentTableProps) {
  if (documents.length === 0) {
    return (
      <EmptyState
        title="文档库为空"
        description="上传 .md、.txt、.json、.csv、.pdf 或 .docx 后，索引进度会出现在这里。"
      />
    );
  }

  return (
    <div className="data-table document-table">
      <div className="data-table__row data-table__row--head">
        <span>Name</span>
        <span>Status</span>
        <span>Chunks</span>
        <span>Vectorized</span>
        <span>Created At</span>
        <span>Progress</span>
      </div>
      {documents.map((document) => (
        <button
          type="button"
          key={document.doc_id}
          className={document.doc_id === selectedDocId ? "data-table__row data-table__row--active" : "data-table__row"}
          onClick={() => onSelectDocument(document.doc_id)}
        >
          <strong>{document.filename}</strong>
          <StatusBadge label={document.status} tone={stateTone(document.status)} />
          <span>{document.chunks === null ? "--" : formatNumber(document.chunks)}</span>
          <span>{document.vectorized ? "Yes" : "No"}</span>
          <TimestampText value={document.created_at} />
          <ProgressBar value={document.progress || (document.status === "READY" ? 100 : 0)} />
        </button>
      ))}
    </div>
  );
}
