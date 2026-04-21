import type { ChangeEvent } from "react";

interface UploadDocumentButtonProps {
  selectedFileName: string | null;
  pending: string | null;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
}

export function UploadDocumentButton({ selectedFileName, pending, onFileChange, onUpload }: UploadDocumentButtonProps) {
  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.target.files?.[0] ?? null);
  }

  return (
    <div className="upload-document-button">
      <label className="file-control">
        <input type="file" accept=".md,.txt,.json,.csv,.pdf,.docx" onChange={handleFileChange} />
        <span>{selectedFileName || "Select document"}</span>
      </label>
      <button type="button" onClick={onUpload} disabled={pending !== null}>
        {pending === "upload" ? "Uploading" : "Upload File"}
      </button>
    </div>
  );
}
