import type { KeyboardEvent } from "react";
import type { DocumentListItem } from "../../types/document";
import { EmptyState } from "../common/EmptyState";
import { ProgressBar } from "../common/ProgressBar";
import { StatusBadge } from "../common/StatusBadge";
import { TimestampText } from "../common/TimestampText";
import { formatNumber, stateTone } from "../../utils/format";

interface DocumentTableProps {
  documents: DocumentListItem[];
  selectedDocId: number | null;
  pending: string | null;
  onSelectDocument: (docId: number) => void;
  onDeleteDocument: (docId: number) => void;
}

export function DocumentTable({
  documents,
  selectedDocId,
  pending,
  onSelectDocument,
  onDeleteDocument,
}: DocumentTableProps) {
  if (documents.length === 0) {
    return (
      <EmptyState
        title="文档库为空"
        description="上传 .md、.txt、.json、.csv、.pdf、.docx 或 .xlsx 后，索引进度会出现在这里。"
      />
    );
  }

  function handleRowKeyDown(event: KeyboardEvent<HTMLDivElement>, docId: number) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelectDocument(docId);
    }
  }

  return (
    <div className="data-table document-table">
      <div className="data-table__row data-table__row--head">
        <span>文件</span>
        <span>状态</span>
        <span>切片</span>
        <span>向量</span>
        <span>创建时间</span>
        <span>进度</span>
        <span>操作</span>
      </div>
      {documents.map((document) => {
        const deleting = pending === `delete-document-${document.doc_id}`;
        return (
          <div
            key={document.doc_id}
            className={document.doc_id === selectedDocId ? "data-table__row data-table__row--active" : "data-table__row"}
            role="button"
            tabIndex={0}
            onClick={() => onSelectDocument(document.doc_id)}
            onKeyDown={(event) => handleRowKeyDown(event, document.doc_id)}
          >
            <strong>{document.filename}</strong>
            <StatusBadge label={document.status} tone={stateTone(document.status)} />
            <span>{document.chunks === null ? "--" : formatNumber(document.chunks)}</span>
            <span>{document.vectorized ? "是" : "否"}</span>
            <TimestampText value={document.created_at} />
            <ProgressBar value={document.progress || (document.status === "READY" ? 100 : 0)} />
            <button
              type="button"
              className="button-danger button-compact"
              disabled={deleting}
              onClick={(event) => {
                event.stopPropagation();
                onDeleteDocument(document.doc_id);
              }}
            >
              {deleting ? "删除中" : "删除"}
            </button>
          </div>
        );
      })}
    </div>
  );
}
