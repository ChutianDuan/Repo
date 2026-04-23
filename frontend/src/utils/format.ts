export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return `${Math.round(value)}%`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return new Intl.NumberFormat("zh-CN").format(value);
}

export function formatBytesGb(used: number | null | undefined, total: number | null | undefined): string {
  if (used === null || used === undefined || total === null || total === undefined) {
    return "--";
  }
  return `${used.toFixed(1)} / ${total.toFixed(1)} GB`;
}

export function formatScore(score: number): string {
  return Number.isFinite(score) ? score.toFixed(3) : "--";
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "--";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("zh-CN", { hour12: false });
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function formatDurationMs(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return `${Math.round(value)}ms`;
}

export function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function formatCurrencyUsd(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return `$${value.toFixed(value >= 1 ? 2 : 6)}`;
}

export function stateTone(state: string | null | undefined): "ok" | "warn" | "error" | "muted" {
  const normalized = (state || "").toUpperCase();
  if (["OK", "SUCCESS", "READY", "HEALTHY"].includes(normalized)) {
    return "ok";
  }
  if (["FAILURE", "FAILED", "ERROR", "UNHEALTHY"].includes(normalized)) {
    return "error";
  }
  if (["STARTED", "PROGRESS", "PROCESSING", "PENDING", "UPLOADED"].includes(normalized)) {
    return "warn";
  }
  return "muted";
}
