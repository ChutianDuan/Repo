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
