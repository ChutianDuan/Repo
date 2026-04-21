import type { ApiEnvelope } from "../types/api";

export function joinUrl(baseUrl: string, path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const normalizedBase = baseUrl.trim().replace(/\/$/, "");
  return `${normalizedBase}${normalizedPath}`;
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
  if (typeof record.detail === "string") {
    return record.detail;
  }
  if (record.detail && typeof record.detail === "object") {
    const detail = record.detail as Record<string, unknown>;
    if (typeof detail.message === "string") {
      return detail.message;
    }
  }

  return fallback;
}

async function parseJsonPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { message: text };
  }
}

export async function requestJson<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(joinUrl(baseUrl, path), init);
  const payload = await parseJsonPayload(response);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, `${response.status} ${response.statusText}`));
  }

  return payload as T;
}

export async function requestEnvelope<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const payload = await requestJson<ApiEnvelope<T>>(baseUrl, path, init);
  return payload.data;
}
