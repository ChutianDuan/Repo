export interface Session {
  session_id: number;
  user_id: number;
  title: string;
  summary?: string;
  created_at: string;
  updated_at?: string;
}

export interface MessageListData {
  session_id: number;
  items: import("./message").ChatMessage[];
}

export interface ChatSubmitData {
  message_id: number;
  task_id: string;
  db_task_id: number;
  state: string;
  status_url: string;
}

export interface SessionSummary {
  session_id: number;
  title: string;
  updated_at?: string | null;
  message_count: number;
  status?: "active" | "idle";
}
