import { requestJson } from "./apiClient";
import type { TaskListResponse, TaskRecord, TaskStatus } from "../types/task";

export function getTaskStatus(baseUrl: string, taskId: string): Promise<TaskStatus> {
  return requestJson<TaskStatus>(baseUrl, `/v1/tasks/${taskId}`);
}

export async function listTasks(baseUrl: string, limit = 50): Promise<TaskRecord[]> {
  const payload = await requestJson<TaskListResponse>(
    baseUrl,
    `/v1/tasks?limit=${encodeURIComponent(String(limit))}`,
  );
  return payload.items;
}
