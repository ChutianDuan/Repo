export interface TaskStatus {
  task_id: string;
  state: string;
  progress: number;
  meta?: Record<string, unknown> | null;
  error?: string | null;
}

export type TaskKind =
  | "ingest_document"
  | "chat_generate"
  | "embedding"
  | "indexing"
  | "ping"
  | "system";

export interface TaskRecord extends TaskStatus {
  db_task_id?: number;
  type: TaskKind | string;
  entity_type: string;
  entity_id: number;
  created_at: string;
  updated_at?: string | null;
}

export interface TaskListResponse {
  items: TaskRecord[];
}
