export interface UploadDocumentResponse {
  doc_id: number;
  filename: string;
  status: string;
}

export interface IngestResponse {
  db_task_id: number;
  task_id: string;
  state: string;
  status_url?: string;
}