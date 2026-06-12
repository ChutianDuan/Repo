export interface UploadDocumentResponse {
  doc_id: number;
  filename: string;
  status?: string;
  index_status?: string | null;
  task_id: string;
  db_task_id: number;
  state: string;
  status_url: string;
}

export interface DeletedDocumentResponse {
  doc_id: number;
  deleted: boolean;
  deleted_files: string[];
  deleted_documents: number;
  deleted_indexes: number;
  deleted_chunks: number;
  deleted_citations: number;
}

export interface DocumentDetail {
  doc_id: number;
  user_id: number;
  filename: string;
  mime: string;
  size_bytes: number;
  status: string;
  index_status?: string | null;
  storage_path: string;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export type DocumentStatus = "UPLOADED" | "PROCESSING" | "INGESTING" | "READY" | "FAILED" | "uploaded" | "parsing" | "parsed" | "indexing" | "indexed" | "failed";

export interface DocumentListItem {
  doc_id: number;
  user_id?: number;
  filename: string;
  status: DocumentStatus;
  chunks: number | null;
  vectorized: boolean;
  created_at: string;
  updated_at?: string | null;
  task_id?: string;
  progress?: number;
  error?: string | null;
  error_message?: string | null;
  index_status?: string | null;
}

export interface DocumentListResponse {
  items: DocumentListItem[];
}
