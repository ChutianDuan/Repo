export const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.trim() || "";
export const POLL_INTERVAL_MS = 1500;
export const POLL_MAX_ROUNDS = 80;
export const SUPPORTED_DOCUMENT_RE = /\.(md|txt|json|csv|pdf|docx|xlsx)$/i;
