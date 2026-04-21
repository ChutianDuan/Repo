export interface UploadDocumentResponse {
  doc_id: number;
  filename: string;
  task_id: string;
  db_task_id: number;
  state: string;
  status_url: string;
}

export interface DocumentDetail {
  doc_id: number;
  user_id: number;
  filename: string;
  mime: string;
  size_bytes: number;
  status: string;
  storage_path: string;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export type DocumentStatus = "UPLOADED" | "PROCESSING" | "READY" | "FAILED";

export interface DocumentListItem {
  doc_id: number;
  filename: string;
  status: DocumentStatus;
  chunks: number | null;
  vectorized: boolean;
  created_at: string;
  updated_at?: string | null;
  task_id?: string;
  progress?: number;
  error?: string | null;
}
