import { joinUrl, requestEnvelope } from "./apiClient";
import type { ChatMessage } from "../types/message";
import type { ChatSubmitData, MessageListData, Session } from "../types/session";

export function createSession(
  baseUrl: string,
  userId: number,
  title: string,
): Promise<Session> {
  return requestEnvelope<Session>(baseUrl, "/v1/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, title }),
  });
}

export function submitChat(
  baseUrl: string,
  sessionId: number,
  docId: number,
  content: string,
  topK: number,
): Promise<ChatSubmitData> {
  return requestEnvelope<ChatSubmitData>(
    baseUrl,
    `/v1/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId, content, top_k: topK }),
    },
  );
}

export async function listMessages(baseUrl: string, sessionId: number): Promise<ChatMessage[]> {
  const data = await requestEnvelope<MessageListData>(
    baseUrl,
    `/v1/sessions/${sessionId}/messages`,
  );
  return data.items;
}

export interface StreamChatRequest {
  session_id: number;
  doc_id: number;
  content: string;
  top_k: number;
}

export interface StreamChatDoneMeta {
  assistant_message_id?: number;
  answer_source?: string;
  context_mode?: string;
  retrieved_count?: number;
  citation_count?: number;
  retrieval_ms?: number;
  ttft_ms?: number;
  e2e_latency_ms?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  cost_usd?: number;
  no_context?: boolean;
}

interface StreamChatCallbacks {
  onDelta?: (delta: string) => void;
  onDone?: (meta: StreamChatDoneMeta) => void;
}

function appendDecodedText(
  current: string,
  chunk: Uint8Array,
  decoder: TextDecoder,
): string {
  return (current + decoder.decode(chunk, { stream: true })).replace(/\r\n/g, "\n");
}

function processSseEvent(rawEvent: string, callbacks: StreamChatCallbacks): boolean {
  const lines = rawEvent.split("\n");
  const dataLines = lines
    .map((line) => line.trim())
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim());

  if (dataLines.length === 0) {
    return false;
  }

  const payloadText = dataLines.join("\n");
  const payload = JSON.parse(payloadText) as {
    type?: string;
    delta?: string;
    message?: string;
    meta?: StreamChatDoneMeta;
  };

  if (payload.type === "delta") {
    callbacks.onDelta?.(payload.delta || "");
    return false;
  }

  if (payload.type === "done") {
    callbacks.onDone?.(payload.meta || {});
    return true;
  }

  if (payload.type === "error") {
    throw new Error(payload.message || "stream error");
  }

  return false;
}

export async function streamChat(
  baseUrl: string,
  request: StreamChatRequest,
  callbacks: StreamChatCallbacks = {},
): Promise<void> {
  const response = await fetch(joinUrl(baseUrl, "/v1/chat/stream"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }

  if (!response.body) {
    throw new Error("stream response body is empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawDone = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer = appendDecodedText(buffer, value, decoder);
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      sawDone = processSseEvent(rawEvent, callbacks) || sawDone;
    }
  }

  if (buffer.trim()) {
    sawDone = processSseEvent(buffer.trim(), callbacks) || sawDone;
  }

  if (!sawDone) {
    throw new Error("stream closed before done event");
  }
}
