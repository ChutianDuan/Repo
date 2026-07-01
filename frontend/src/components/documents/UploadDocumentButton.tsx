import type { ChangeEvent } from "react";

interface UploadDocumentButtonProps {
  selectedFileName: string | null;
  webUrl: string;
  pending: string | null;
  onFileChange: (file: File | null) => void;
  onWebUrlChange: (url: string) => void;
  onUpload: () => void;
  onUploadWebDocument: () => void;
}

export function UploadDocumentButton({
  selectedFileName,
  webUrl,
  pending,
  onFileChange,
  onWebUrlChange,
  onUpload,
  onUploadWebDocument,
}: UploadDocumentButtonProps) {
  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.target.files?.[0] ?? null);
  }

  return (
    <div className="upload-document-button">
      <div className="upload-document-button__group">
        <label className="file-control">
          <input type="file" accept=".md,.txt,.json,.csv,.pdf,.docx,.xlsx" onChange={handleFileChange} />
          <span>{selectedFileName || "Select document"}</span>
        </label>
        <button type="button" onClick={onUpload} disabled={pending !== null}>
          {pending === "upload" ? "Uploading" : "Upload File"}
        </button>
      </div>
      <div className="upload-document-button__group">
        <input
          className="web-url-control"
          type="url"
          value={webUrl}
          placeholder="https://example.com/page"
          onChange={(event) => onWebUrlChange(event.target.value)}
        />
        <button type="button" onClick={onUploadWebDocument} disabled={pending !== null || !webUrl.trim()}>
          {pending === "web-upload" ? "Importing" : "Import URL"}
        </button>
      </div>
    </div>
  );
}
