import { requestEnvelope } from "./apiClient";
import type { UserItem, UserListData } from "../types/user";

export function createUser(baseUrl: string, name: string): Promise<UserItem> {
  return requestEnvelope<UserItem>(baseUrl, "/v1/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function listLatestUsers(baseUrl: string, limit = 6): Promise<UserItem[]> {
  const data = await requestEnvelope<UserListData>(
    baseUrl,
    `/v1/users/latest?limit=${encodeURIComponent(String(limit))}`,
  );
  return data.items;
}
