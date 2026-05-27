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
  content: string,
  topK: number,
): Promise<ChatSubmitData> {
  return requestEnvelope<ChatSubmitData>(
    baseUrl,
    `/v1/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, top_k: topK }),
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
  doc_id?: number;
  doc_ids?: number[];
  content: string;
  top_k: number;
}

export interface StreamChatDoneMeta {
  run_id?: number;
  agent_run_id?: number;
  assistant_message_id?: number;
  message_id?: number;
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
  doc_ids?: number[];
  steps_used?: number;
}

export interface AgentChatStreamRequest {
  session_id: number;
  message: string;
  trace_id?: string;
}

export interface AgentStepEvent {
  type: "agent_step";
  run_id?: number;
  step_id?: number;
  step_index?: number;
  step_type?: string;
  name?: string;
  status?: string;
  decision?: string;
  answer?: string;
  latency_ms?: number;
  tool_call_count?: number;
  [key: string]: unknown;
}

export interface AgentToolCallEvent {
  type: "tool_call";
  run_id?: number;
  step_id?: number;
  tool_call_row_id?: number;
  tool_call_id?: string;
  tool_name?: string;
  arguments?: unknown;
  status?: string;
  latency_ms?: number;
  [key: string]: unknown;
}

export interface AgentToolResultEvent {
  type: "tool_result";
  run_id?: number;
  step_id?: number;
  tool_call_row_id?: number;
  tool_call_id?: string;
  tool_name?: string;
  arguments?: unknown;
  result?: unknown;
  status?: string;
  error_message?: string;
  latency_ms?: number;
  [key: string]: unknown;
}

export interface AgentFinalEvent {
  type: "final";
  run_id?: number;
  message_id?: number;
  answer: string;
  citations?: unknown[];
  steps_used?: number;
  e2e_latency_ms?: number;
  [key: string]: unknown;
}

export interface StreamChatCallbacks {
  onDelta?: (delta: string) => void;
  onDone?: (meta: StreamChatDoneMeta) => void;
  onAgentStep?: (event: AgentStepEvent) => void;
  onToolCall?: (event: AgentToolCallEvent) => void;
  onToolResult?: (event: AgentToolResultEvent) => void;
  onFinal?: (event: AgentFinalEvent) => void;
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
  const eventName = lines
    .map((line) => line.trim())
    .find((line) => line.startsWith("event:"))
    ?.slice(6)
    .trim();
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
    [key: string]: unknown;
  };
  const type = payload.type || eventName;

  if (type === "delta") {
    callbacks.onDelta?.(payload.delta || "");
    return false;
  }

  if (type === "done") {
    callbacks.onDone?.(payload.meta || {});
    return true;
  }

  if (type === "error") {
    throw new Error(payload.message || "stream error");
  }

  if (type === "agent_step") {
    callbacks.onAgentStep?.({ ...payload, type: "agent_step" } as AgentStepEvent);
    return false;
  }

  if (type === "tool_call") {
    callbacks.onToolCall?.({ ...payload, type: "tool_call" } as AgentToolCallEvent);
    return false;
  }

  if (type === "tool_result") {
    callbacks.onToolResult?.({ ...payload, type: "tool_result" } as AgentToolResultEvent);
    return false;
  }

  if (type === "final") {
    callbacks.onFinal?.({ ...payload, type: "final" } as AgentFinalEvent);
    return false;
  }

  return false;
}

async function streamSse(
  baseUrl: string,
  path: string,
  request: unknown,
  callbacks: StreamChatCallbacks = {},
): Promise<void> {
  const response = await fetch(joinUrl(baseUrl, path), {
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

export async function streamChat(
  baseUrl: string,
  request: StreamChatRequest,
  callbacks: StreamChatCallbacks = {},
): Promise<void> {
  return streamSse(baseUrl, "/v1/chat/stream", request, callbacks);
}

export async function streamAgentChat(
  baseUrl: string,
  request: AgentChatStreamRequest,
  callbacks: StreamChatCallbacks = {},
): Promise<void> {
  return streamSse(
    baseUrl,
    "/v1/agent/chat/stream",
    { ...request, stream: true },
    callbacks,
  );
}
