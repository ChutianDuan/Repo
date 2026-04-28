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

interface DocumentsPageProps {
  documents: DocumentListItem[];
  selectedDocId: number | null;
  tasks: TaskRecord[];
  selectedFileName: string | null;
  pending: string | null;
  onSelectDocument: (docId: number) => void;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
}

type DocumentFilter = "all" | "ready" | "processing" | "failed";

export function DocumentsPage({
  documents,
  selectedDocId,
  tasks,
  selectedFileName,
  pending,
  onSelectDocument,
  onFileChange,
  onUpload,
}: DocumentsPageProps) {
  const [filter, setFilter] = useState<DocumentFilter>("all");
  const filteredDocuments = documents.filter((document) => {
    if (filter === "all") {
      return true;
    }
    if (filter === "ready") {
      return document.status === "READY";
    }
    if (filter === "processing") {
      return document.status === "PROCESSING" || document.status === "UPLOADED";
    }
    return document.status === "FAILED";
  });
  const selectedDocument = documents.find((document) => document.doc_id === selectedDocId) || null;
  const selectedTasks = selectedDocument
    ? tasks.filter((task) => task.entity_type === "document" && task.entity_id === selectedDocument.doc_id)
    : [];
  const readyCount = documents.filter((document) => document.status === "READY").length;
  const processingCount = documents.filter((document) => document.status === "PROCESSING" || document.status === "UPLOADED").length;
  const failedCount = documents.filter((document) => document.status === "FAILED").length;
  const totalChunks = documents.reduce((sum, document) => sum + (document.chunks || 0), 0);

  return (
    <div className="documents-page page-stack">
      <PageTitle
        eyebrow="Knowledge Base"
        title="Documents"
        description="上传文档，查看索引状态与向量化结果。"
        action={
          <UploadDocumentButton
            selectedFileName={selectedFileName}
            pending={pending}
            onFileChange={onFileChange}
            onUpload={onUpload}
          />
        }
      />

      <div className="summary-grid">
        <MetricCard label="Total Docs" value={formatNumber(documents.length)} />
        <MetricCard label="Ready" value={formatNumber(readyCount)} tone="ok" />
        <MetricCard label="Processing" value={formatNumber(processingCount)} tone="warn" />
        <MetricCard label="Failed" value={formatNumber(failedCount)} tone={failedCount > 0 ? "error" : "default"} />
        <MetricCard label="Total Chunks" value={formatNumber(totalChunks)} />
      </div>

      <SectionCard
        title="Document Table"
        description="按状态筛选当前文档。"
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
            onSelectDocument={onSelectDocument}
          />
          <DocumentDetailDrawer document={selectedDocument} tasks={selectedTasks} />
        </div>
      </SectionCard>
    </div>
  );
}
