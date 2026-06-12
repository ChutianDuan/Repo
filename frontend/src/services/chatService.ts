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
  lancedb_ms?: number;
  rerank_ms?: number;
  raw_hit_count?: number;
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

interface ProcessedSseEvent {
  done: boolean;
  eventId: string | null;
}

interface StreamSseOptions {
  resumeOnDisconnect?: boolean;
  maxResumeAttempts?: number;
}

function appendDecodedText(
  current: string,
  chunk: Uint8Array,
  decoder: TextDecoder,
): string {
  return (current + decoder.decode(chunk, { stream: true })).replace(/\r\n/g, "\n");
}

function processSseEvent(rawEvent: string, callbacks: StreamChatCallbacks): ProcessedSseEvent {
  const lines = rawEvent.split("\n");
  const trimmedLines = lines.map((line) => line.trim());
  const eventName = trimmedLines
    .find((line) => line.startsWith("event:"))
    ?.slice(6)
    .trim();
  const eventId = trimmedLines
    .find((line) => line.startsWith("id:"))
    ?.slice(3)
    .trim() || null;
  const dataLines = trimmedLines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim());

  if (dataLines.length === 0) {
    return { done: false, eventId };
  }

  const payloadText = dataLines.join("\n");
  const payload = JSON.parse(payloadText) as {
    type?: string;
    delta?: string;
    message?: string;
    meta?: StreamChatDoneMeta;
    event_id?: string | number;
    [key: string]: unknown;
  };
  const type = payload.type || eventName;
  const nextEventId = eventId || (payload.event_id === undefined ? null : String(payload.event_id));

  if (type === "delta") {
    callbacks.onDelta?.(payload.delta || "");
    return { done: false, eventId: nextEventId };
  }

  if (type === "done") {
    callbacks.onDone?.(payload.meta || {});
    return { done: true, eventId: nextEventId };
  }

  if (type === "error") {
    throw new Error(payload.message || "stream error");
  }

  if (type === "agent_step") {
    callbacks.onAgentStep?.({ ...payload, type: "agent_step" } as AgentStepEvent);
    return { done: false, eventId: nextEventId };
  }

  if (type === "tool_call") {
    callbacks.onToolCall?.({ ...payload, type: "tool_call" } as AgentToolCallEvent);
    return { done: false, eventId: nextEventId };
  }

  if (type === "tool_result") {
    callbacks.onToolResult?.({ ...payload, type: "tool_result" } as AgentToolResultEvent);
    return { done: false, eventId: nextEventId };
  }

  if (type === "final") {
    callbacks.onFinal?.({ ...payload, type: "final" } as AgentFinalEvent);
    return { done: false, eventId: nextEventId };
  }

  return { done: false, eventId: nextEventId };
}

async function streamSse(
  baseUrl: string,
  path: string,
  request: unknown,
  callbacks: StreamChatCallbacks = {},
  options: StreamSseOptions = {},
): Promise<void> {
  const maxResumeAttempts = options.maxResumeAttempts ?? 3;
  let resumeAttempts = 0;
  let lastEventId: string | null = null;

  while (true) {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    };
    if (lastEventId) {
      headers["Last-Event-ID"] = lastEventId;
    }

    let response: Response;
    try {
      response = await fetch(joinUrl(baseUrl, path), {
        method: "POST",
        headers,
        body: JSON.stringify(request),
      });
    } catch (error) {
      if (!options.resumeOnDisconnect || !lastEventId || resumeAttempts >= maxResumeAttempts) {
        throw error;
      }
      resumeAttempts += 1;
      continue;
    }

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
    let readFailed = false;

    while (true) {
      let result: ReadableStreamReadResult<Uint8Array>;
      try {
        result = await reader.read();
      } catch (error) {
        if (!options.resumeOnDisconnect || !lastEventId || resumeAttempts >= maxResumeAttempts) {
          throw error;
        }
        readFailed = true;
        break;
      }

      if (result.done) {
        break;
      }

      buffer = appendDecodedText(buffer, result.value, decoder);
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const rawEvent of events) {
        const processed = processSseEvent(rawEvent, callbacks);
        if (processed.eventId) {
          lastEventId = processed.eventId;
        }
        sawDone = processed.done || sawDone;
      }
    }

    if (!readFailed && buffer.trim()) {
      const processed = processSseEvent(buffer.trim(), callbacks);
      if (processed.eventId) {
        lastEventId = processed.eventId;
      }
      sawDone = processed.done || sawDone;
    }

    if (sawDone) {
      return;
    }

    if (!options.resumeOnDisconnect || !lastEventId || resumeAttempts >= maxResumeAttempts) {
      throw new Error("stream closed before done event");
    }

    resumeAttempts += 1;
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
    { resumeOnDisconnect: true },
  );
}
