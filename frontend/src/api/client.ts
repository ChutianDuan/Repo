import type { ApiEnvelope, HealthSnapshot } from "../types/api";
import type { UploadDocumentResponse } from "../types/document";
import type { ChatMessage } from "../types/message";
import type { ChatSubmitData, MessageListData, Session } from "../types/session";
import type { TaskStatus } from "../types/task";
import type { UserItem, UserListData } from "../types/user";

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") {
    return fallback;
  }

  const record = payload as Record<string, unknown>;

  if (typeof record.message === "string") {
    return record.message;
  }
  if (typeof record.error === "string") {
    return record.error;
  }
  if (record.detail && typeof record.detail === "object") {
    const detail = record.detail as Record<string, unknown>;
    if (typeof detail.message === "string") {
      return detail.message;
    }
  }
  if (typeof record.detail === "string") {
    return record.detail;
  }

  return fallback;
}

async function requestJson<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(joinUrl(baseUrl, path), init);
  const text = await response.text();
  const payload = text ? (JSON.parse(text) as unknown) : {};

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, `${response.status} ${response.statusText}`));
  }

  return payload as T;
}

export function getHealth(baseUrl: string): Promise<HealthSnapshot> {
  return fetch(joinUrl(baseUrl, "/health"))
    .then(async (response) => {
      const text = await response.text();
      if (!text) {
        throw new Error("health response is empty");
      }
      return JSON.parse(text) as HealthSnapshot;
    });
}

export function getTaskStatus(baseUrl: string, taskId: string): Promise<TaskStatus> {
  return requestJson<TaskStatus>(baseUrl, `/v1/tasks/${taskId}`);
}

export async function createUser(baseUrl: string, name: string): Promise<UserItem> {
  const payload = await requestJson<ApiEnvelope<UserItem>>(baseUrl, "/v1/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

  return payload.data;
}

export async function listLatestUsers(baseUrl: string, limit = 5): Promise<UserItem[]> {
  const payload = await requestJson<ApiEnvelope<UserListData>>(
    baseUrl,
    `/v1/users/latest?limit=${encodeURIComponent(String(limit))}`,
  );

  return payload.data.items;
}

export async function uploadDocument(
  baseUrl: string,
  userId: number,
  file: File,
): Promise<UploadDocumentResponse> {
  const formData = new FormData();
  formData.append("user_id", String(userId));
  formData.append("file", file);

  return requestJson<UploadDocumentResponse>(baseUrl, "/v1/documents", {
    method: "POST",
    body: formData,
  });
}

export async function createSession(
  baseUrl: string,
  userId: number,
  title: string,
): Promise<Session> {
  const payload = await requestJson<ApiEnvelope<Session>>(baseUrl, "/v1/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, title }),
  });

  return payload.data;
}

export async function submitChat(
  baseUrl: string,
  sessionId: number,
  docId: number,
  content: string,
  topK: number,
): Promise<ChatSubmitData> {
  const payload = await requestJson<ApiEnvelope<ChatSubmitData>>(
    baseUrl,
    `/v1/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId, content, top_k: topK }),
    },
  );

  return payload.data;
}

export async function listMessages(baseUrl: string, sessionId: number): Promise<ChatMessage[]> {
  const payload = await requestJson<ApiEnvelope<MessageListData>>(
    baseUrl,
    `/v1/sessions/${sessionId}/messages`,
  );
  return payload.data.items;
}
