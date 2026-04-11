import type { Citation } from "./citation";

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  message_id: number;
  session_id: number;
  role: MessageRole;
  content: string;
  status: string;
  citations: Citation[];
  meta?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
