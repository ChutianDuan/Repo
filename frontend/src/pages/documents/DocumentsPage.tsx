import { useState } from "react";
import type { DocumentListItem } from "../../types/document";
import type { TaskRecord } from "../../types/task";
import { DocumentDetailDrawer } from "../../components/documents/DocumentDetailDrawer";
import { DocumentTable } from "../../components/documents/DocumentTable";
import { UploadDocumentButton } from "../../components/documents/UploadDocumentButton";
import { MetricCard } from "../../components/common/MetricCard";
import { PageTitle } from "../../components/common/PageTitle";
import { SectionCard } from "../../components/common/SectionCard";
import { formatNumber } from "../../utils/format";
import { isFailedDocument, isIndexedDocument, isProcessingDocument } from "../../app/appState";

interface DocumentsPageProps {
  documents: DocumentListItem[];
  selectedDocId: number | null;
  tasks: TaskRecord[];
  selectedFileName: string | null;
  webUrl: string;
  pending: string | null;
  onSelectDocument: (docId: number) => void;
  onFileChange: (file: File | null) => void;
  onWebUrlChange: (url: string) => void;
  onUpload: () => void;
  onUploadWebDocument: () => void;
  onDeleteDocument: (docId: number) => void;
}

type DocumentFilter = "all" | "ready" | "processing" | "failed";

export function DocumentsPage({
  documents,
  selectedDocId,
  tasks,
  selectedFileName,
  webUrl,
  pending,
  onSelectDocument,
  onFileChange,
  onWebUrlChange,
  onUpload,
  onUploadWebDocument,
  onDeleteDocument,
}: DocumentsPageProps) {
  const [filter, setFilter] = useState<DocumentFilter>("all");
  const filteredDocuments = documents.filter((document) => {
    if (filter === "all") {
      return true;
    }
    if (filter === "ready") {
      return isIndexedDocument(document);
    }
    if (filter === "processing") {
      return isProcessingDocument(document);
    }
    return isFailedDocument(document);
  });
  const selectedDocument = documents.find((document) => document.doc_id === selectedDocId) || null;
  const selectedTasks = selectedDocument
    ? tasks.filter((task) => task.entity_type === "document" && task.entity_id === selectedDocument.doc_id)
    : [];
  const readyCount = documents.filter(isIndexedDocument).length;
  const processingCount = documents.filter(isProcessingDocument).length;
  const failedCount = documents.filter(isFailedDocument).length;
  const totalChunks = documents.reduce((sum, document) => sum + (document.chunks || 0), 0);

  return (
    <div className="documents-page page-stack">
      <PageTitle
        eyebrow="文档索引"
        title="笔记文档"
        description="上传笔记文档，等待 index_status indexed 后即可在问答页检索；不需要的文档可以直接删除。"
        action={
          <UploadDocumentButton
            selectedFileName={selectedFileName}
            webUrl={webUrl}
            pending={pending}
            onFileChange={onFileChange}
            onWebUrlChange={onWebUrlChange}
            onUpload={onUpload}
            onUploadWebDocument={onUploadWebDocument}
          />
        }
      />

      <div className="summary-grid">
        <MetricCard label="文档总数" value={formatNumber(documents.length)} />
        <MetricCard label="可检索" value={formatNumber(readyCount)} tone="ok" />
        <MetricCard label="处理中" value={formatNumber(processingCount)} tone="warn" />
        <MetricCard label="失败" value={formatNumber(failedCount)} tone={failedCount > 0 ? "error" : "default"} />
        <MetricCard label="切片数" value={formatNumber(totalChunks)} />
      </div>

      <SectionCard
        title="文档列表"
        description="查看上传、索引和删除状态。"
        action={
          <div className="filter-tabs">
            {(["all", "ready", "processing", "failed"] as DocumentFilter[]).map((item) => (
              <button
                key={item}
                type="button"
                className={filter === item ? "filter-tab filter-tab--active" : "filter-tab"}
                onClick={() => setFilter(item)}
              >
                {item}
              </button>
            ))}
          </div>
        }
      >
        <div className="split-panel">
          <DocumentTable
            documents={filteredDocuments}
            selectedDocId={selectedDocId}
            pending={pending}
            onSelectDocument={onSelectDocument}
            onDeleteDocument={onDeleteDocument}
          />
          <DocumentDetailDrawer document={selectedDocument} tasks={selectedTasks} />
        </div>
      </SectionCard>
    </div>
  );
}
