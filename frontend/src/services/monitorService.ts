import { joinUrl, requestJson } from "./apiClient";
import type { HealthSnapshot } from "../types/api";
import type { MonitorOverview } from "../types/monitor";

export async function getHealth(baseUrl: string): Promise<HealthSnapshot> {
  const response = await fetch(joinUrl(baseUrl, "/health"));
  const text = await response.text();

  if (!response.ok) {
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  if (!text) {
    throw new Error("health response is empty");
  }

  return JSON.parse(text) as HealthSnapshot;
}

export function getMonitorOverview(baseUrl: string): Promise<MonitorOverview> {
  return requestJson<unknown>(baseUrl, "/v1/monitor/overview").then((payload) => {
    if (
      !payload ||
      typeof payload !== "object" ||
      !("services" in payload) ||
      !("queue" in payload) ||
      !("rag" in payload)
    ) {
      throw new Error("monitor overview response is not available");
    }

    return payload as MonitorOverview;
  });
}
