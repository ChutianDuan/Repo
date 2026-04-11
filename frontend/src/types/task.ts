export interface TaskStatus {
  task_id: string;
  state: string;
  progress: number;
  meta?: Record<string, unknown> | null;
  error?: string | null;
}
