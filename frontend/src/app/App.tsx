import { useEffect, useState } from "react";

import {
  DEFAULT_API_BASE_URL,
  POLL_INTERVAL_MS,
  POLL_MAX_ROUNDS,
  SUPPORTED_DOCUMENT_RE,
} from "./appConfig";
import {
  buildFallbackOverview,
  buildLocalMessage,
  buildMetricPoint,
  getChunkCount,
  isIndexedDocument,
  isTerminalTask,
  normalizeTopK,
  parsePositiveInteger,
  sleep,
  taskRecordFromStatus,
} from "./appState";
import { useHashRoute } from "./router";
import { AppShell } from "../components/layout/AppShell";
import { DocumentsPage } from "../pages/documents/DocumentsPage";
import { MonitorPage } from "../pages/monitor/MonitorPage";
import { SettingsPage } from "../pages/settings/SettingsPage";
import { TasksPage } from "../pages/tasks/TasksPage";
import { WorkspacePage } from "../pages/workspace/WorkspacePage";
import {
  createSession,
  listMessages,
  streamAgentChat,
  streamChat,
  submitChat,
  type AgentFinalEvent,
  type AgentStepEvent,
  type AgentToolCallEvent,
  type AgentToolResultEvent,
  type StreamChatCallbacks,
  type StreamChatDoneMeta,
} from "../services/chatService";
import { deleteDocument, listDocuments, uploadDocument, uploadWebDocument } from "../services/documentService";
import { getHealth, getMonitorOverview } from "../services/monitorService";
import { getTaskStatus, listTasks } from "../services/taskService";
import { createUser, listLatestUsers } from "../services/userService";
import { usePolling } from "../hooks/usePolling";
import type { HealthSnapshot } from "../types/api";
import type { DocumentListItem, UploadDocumentResponse } from "../types/document";
import type { Citation } from "../types/citation";
import type { ChatMessage } from "../types/message";
import type { MetricPoint, MonitorOverview } from "../types/monitor";
import type { Session, SessionSummary } from "../types/session";
import type { TaskRecord, TaskStatus } from "../types/task";
import type { UserItem } from "../types/user";
import { nowIso } from "../utils/format";
import type { PendingAction } from "./appState";
import type { AgentTraceRow, RetrievalTraceDetails, TraceCitation } from "../components/AgentTracePanel";

type AgentTracePatch = Omit<AgentTraceRow, "step">;

function summarizeValue(value: unknown, maxLength = 140): string {
  if (value === null || value === undefined) {
    return "";
  }
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (!text) {
    return "";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function getRetrievalTrace(result: unknown): RetrievalTraceDetails | undefined {
  if (!result || typeof result !== "object") {
    return undefined;
  }
  const retrieval = (result as { retrieval?: unknown }).retrieval;
  if (!retrieval || typeof retrieval !== "object") {
    return undefined;
  }
  const item = retrieval as Record<string, unknown>;
  return {
    provider: typeof item.provider === "string" ? item.provider : undefined,
    denseTopK: asNumber(item.dense_top_k),
    rerankTopK: asNumber(item.rerank_top_k),
    candidateCount: asNumber(item.candidate_count),
    vectorSearchLatencyMs: asNumber(item.vector_search_latency_ms),
    rerankLatencyMs: asNumber(item.rerank_latency_ms),
    retrievalLatencyMs: asNumber(item.retrieval_latency_ms),
  };
}

function normalizeCitation(value: unknown): Citation | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const item = value as Record<string, unknown>;
  const docId = asNumber(item.doc_id ?? item.document_id);
  const chunkId = asNumber(item.chunk_id ?? item.id);
  const chunkIndex = asNumber(item.chunk_index ?? item.index ?? item.seq);
  if (docId === null || chunkId === null || chunkIndex === null) {
    return null;
  }
  return {
    citation_id: asNumber(item.citation_id) ?? undefined,
    doc_id: docId,
    chunk_id: chunkId,
    chunk_index: chunkIndex,
    score: asNumber(item.score) ?? 0,
    snippet: String(item.snippet ?? item.content ?? ""),
    created_at: typeof item.created_at === "string" ? item.created_at : undefined,
  };
}

function normalizeCitations(value: unknown): Citation[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map(normalizeCitation).filter((item): item is Citation => item !== null);
}

function getResultCitations(result: unknown): TraceCitation[] {
  if (!result || typeof result !== "object") {
    return [];
  }
  const results = (result as { results?: unknown }).results;
  if (!Array.isArray(results)) {
    return [];
  }
  return results.map((value) => {
    const item = value && typeof value === "object" ? value as Record<string, unknown> : {};
    return {
      docId: asNumber(item.doc_id ?? item.document_id),
      chunkId: asNumber(item.chunk_id ?? item.id),
      chunkIndex: asNumber(item.chunk_index ?? item.index ?? item.seq),
      score: asNumber(item.score),
      snippet: String(item.snippet ?? item.content ?? ""),
      title: typeof item.title === "string" ? item.title : undefined,
    };
  });
}

function getResultCount(result: unknown): number | null {
  if (!result || typeof result !== "object") {
    return null;
  }
  const data = result as { total?: unknown; results?: unknown };
  if (typeof data.total === "number") {
    return data.total;
  }
  if (Array.isArray(data.results)) {
    return data.results.length;
  }
  return null;
}

function getResultError(result: unknown): string | null {
  if (!result || typeof result !== "object") {
    return null;
  }
  const error = (result as { error?: unknown }).error;
  return typeof error === "string" && error.trim() ? error.trim() : null;
}

function isTerminalTraceStatus(status: string | undefined): boolean {
  return ["SUCCESS", "FAILED", "FAILURE", "ERROR", "CANCELLED"].includes(String(status || "").toUpperCase());
}

function normalizeTraceStatus(status: string | undefined, fallback = "RUNNING"): string {
  return String(status || fallback).toUpperCase();
}

export default function App() {
  const [route, navigate] = useHashRoute();
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [userId, setUserId] = useState("1");
  const [newUserName, setNewUserName] = useState("");
  const [topK, setTopKState] = useState(3);
  const [ragEnabled, setRagEnabled] = useState(true);
  const [streamingEnabled, setStreamingEnabled] = useState(true);
  const [chunkSize, setChunkSize] = useState("800");
  const [chunkOverlap, setChunkOverlap] = useState("120");
  const [modelName, setModelName] = useState("local-llm");
  const [question, setQuestion] = useState("这份文档讲了什么？");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [webUrl, setWebUrl] = useState("");

  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [apiLatencyMs, setApiLatencyMs] = useState<number | null>(null);
  const [latestUsers, setLatestUsers] = useState<UserItem[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [messagesBySession, setMessagesBySession] = useState<Record<number, ChatMessage[]>>({});
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [currentDocumentId, setCurrentDocumentId] = useState<number | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [taskRecords, setTaskRecords] = useState<TaskRecord[]>([]);
  const [ingestTask, setIngestTask] = useState<TaskStatus | null>(null);
  const [chatTask, setChatTask] = useState<TaskStatus | null>(null);
  const [agentTraceRows, setAgentTraceRows] = useState<AgentTraceRow[]>([]);
  const [monitorOverview, setMonitorOverview] = useState<MonitorOverview | null>(null);
  const [metricPoints, setMetricPoints] = useState<MetricPoint[]>([]);
  const [pending, setPending] = useState<PendingAction>(null);
  const [refreshingHealth, setRefreshingHealth] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taskListError, setTaskListError] = useState<string | null>(null);
  const [monitorError, setMonitorError] = useState<string | null>(null);

  const currentMessages = session ? messagesBySession[session.session_id] || [] : [];
  const readyDocuments = documents.filter(isIndexedDocument);
  const overview = monitorOverview || buildFallbackOverview(health, taskRecords, documents, apiLatencyMs, topK);
  const selectedFileName = selectedFile?.name || null;

  function setTopK(value: number) {
    setTopKState(normalizeTopK(value));
  }

  function recordMetricPoint(nextOverview: MonitorOverview) {
    const fallbackThroughput = taskRecords.filter((task) => task.state === "SUCCESS").length;
    setMetricPoints((current) => [
      ...current.slice(-17),
      buildMetricPoint(nextOverview, fallbackThroughput),
    ]);
  }

  function upsertTaskRecord(status: TaskStatus, defaults: Partial<TaskRecord>) {
    setTaskRecords((current) => {
      const existing = current.find((task) => task.task_id === status.task_id);
      const nextTask = taskRecordFromStatus(status, existing, defaults);
      return [nextTask, ...current.filter((task) => task.task_id !== status.task_id)];
    });
  }

  function updateSessionSummary(sessionId: number, messages: ChatMessage[]) {
    const lastMessage = messages[messages.length - 1];
    setSessions((current) =>
      current.map((item) =>
        item.session_id === sessionId
          ? {
              ...item,
              message_count: messages.length,
              updated_at: lastMessage?.updated_at || lastMessage?.created_at || item.updated_at,
              status: "active",
            }
          : item,
      ),
    );
  }

  function setMessagesForSession(sessionId: number, messages: ChatMessage[]) {
    setMessagesBySession((current) => ({ ...current, [sessionId]: messages }));
    updateSessionSummary(sessionId, messages);
  }

  function updateMessagesForSession(
    sessionId: number,
    updater: (messages: ChatMessage[]) => ChatMessage[],
  ) {
    setMessagesBySession((current) => {
      const nextMessages = updater(current[sessionId] || []);
      updateSessionSummary(sessionId, nextMessages);
      return { ...current, [sessionId]: nextMessages };
    });
  }

  function upsertAgentTraceRow(patch: AgentTracePatch) {
    const now = performance.now();
    setAgentTraceRows((current) => {
      const index = current.findIndex((row) => row.id === patch.id);
      const status = normalizeTraceStatus(patch.status);

      if (index >= 0) {
        const next = current.map((row, rowIndex) => {
          if (rowIndex !== index) {
            return row;
          }

          const updated: AgentTraceRow = {
            ...row,
            ...patch,
            status,
          };
          if (!updated.startedAtMs && !isTerminalTraceStatus(status)) {
            updated.startedAtMs = now;
          }
          if (updated.latencyMs === undefined && row.startedAtMs && isTerminalTraceStatus(status)) {
            updated.latencyMs = Math.max(1, Math.round(now - row.startedAtMs));
          }
          return updated;
        });

        return next.map((row, rowIndex) => ({ ...row, step: rowIndex + 1 }));
      }

      const row: AgentTraceRow = {
        ...patch,
        step: current.length + 1,
        status,
        startedAtMs: patch.startedAtMs ?? (isTerminalTraceStatus(status) ? undefined : now),
      };
      return [...current, row].map((item, rowIndex) => ({ ...item, step: rowIndex + 1 }));
    });
  }

  function startAgentTrace(prompt: string) {
    setAgentTraceRows([
      {
        id: "agent-decision",
        step: 1,
        type: "agent_step",
        tool: "-",
        input: summarizeValue(prompt),
        output: "Agent 正在判断是否需要检索",
        status: "RUNNING",
        startedAtMs: performance.now(),
      },
    ]);
  }

  function agentToolTraceId(event: AgentToolCallEvent | AgentToolResultEvent): string {
    return String(event.tool_call_id || event.tool_call_row_id || event.tool_name || "knowledge_search");
  }

  function handleAgentStepEvent(event: AgentStepEvent, prompt: string) {
    const status = normalizeTraceStatus(event.status);
    const stepIndex = Number(event.step_index ?? 0);

    if (stepIndex === 0 && status === "RUNNING") {
      upsertAgentTraceRow({
        id: "agent-decision",
        type: event.step_type || "agent_step",
        tool: "-",
        input: summarizeValue(prompt),
        output: "Agent 正在判断是否需要检索",
        status,
      });
      return;
    }

    if (event.decision === "tool_call") {
      upsertAgentTraceRow({
        id: "agent-decision",
        type: event.step_type || "agent_step",
        tool: "-",
        input: summarizeValue(prompt),
        output: "需要检索",
        latencyMs: event.latency_ms,
        status: "SUCCESS",
      });
      return;
    }

    if (stepIndex > 0 && status === "RUNNING") {
      upsertAgentTraceRow({
        id: "agent-generation",
        type: event.step_type || "agent_step",
        tool: "-",
        input: "检索结果",
        output: "正在生成答案",
        status,
      });
      return;
    }

    if (event.decision === "final_answer" || event.answer) {
      const answeredDirectly = stepIndex === 0;
      upsertAgentTraceRow({
        id: answeredDirectly ? "agent-decision" : "agent-generation",
        type: event.step_type || "agent_step",
        tool: "-",
        input: answeredDirectly ? summarizeValue(prompt) : "检索结果",
        output: answeredDirectly ? "无需检索，直接回答" : "答案已生成",
        latencyMs: event.latency_ms,
        status: "SUCCESS",
      });
    }
  }

  function handleAgentToolCallEvent(event: AgentToolCallEvent) {
    const toolName = event.tool_name || "knowledge_search";
    upsertAgentTraceRow({
      id: "agent-decision",
      type: "agent_step",
      tool: "-",
      output: "需要检索",
      status: "SUCCESS",
    });
    upsertAgentTraceRow({
      id: `tool-call-${agentToolTraceId(event)}`,
      type: "tool_call",
      tool: toolName,
      input: summarizeValue(event.arguments),
      output: `调用 ${toolName}`,
      latencyMs: event.latency_ms,
      status: normalizeTraceStatus(event.status),
    });
  }

  function handleAgentToolResultEvent(event: AgentToolResultEvent) {
    const toolName = event.tool_name || "knowledge_search";
    const resultCount = getResultCount(event.result);
    const errorMessage = event.error_message || getResultError(event.result);
    const output = errorMessage
      ? `工具失败：${errorMessage}`
      : resultCount === null
        ? "获得工具结果"
        : `获得 ${resultCount} 条结果`;
    const status = normalizeTraceStatus(event.status, "SUCCESS");
    const retrieval = getRetrievalTrace(event.result);
    const citations = getResultCitations(event.result);

    upsertAgentTraceRow({
      id: `tool-call-${agentToolTraceId(event)}`,
      type: "tool_call",
      tool: toolName,
      input: summarizeValue(event.arguments),
      output: `调用 ${toolName}`,
      latencyMs: event.latency_ms,
      status,
    });
    upsertAgentTraceRow({
      id: `tool-result-${agentToolTraceId(event)}`,
      type: "tool_result",
      tool: toolName,
      input: "-",
      output,
      latencyMs: event.latency_ms,
      status,
      retrieval,
      citations,
    });
    upsertAgentTraceRow({
      id: "agent-generation",
      type: "agent_step",
      tool: "-",
      input: output,
      output: status === "FAILED" ? "检索失败，正在降级生成答案" : "正在生成答案",
      status: "RUNNING",
    });
  }

  function handleAgentFinalEvent(_event: AgentFinalEvent) {
    upsertAgentTraceRow({
      id: "agent-generation",
      type: "agent_step",
      tool: "-",
      input: "检索结果",
      output: "答案已生成",
      status: "SUCCESS",
    });
  }

  function updateDocumentFromTask(docId: number, task: TaskStatus) {
    const chunkCount = getChunkCount(task.meta);
    const metaIndexStatus = typeof task.meta?.index_status === "string" ? task.meta.index_status : null;
    const nextIndexStatus =
      metaIndexStatus || (task.state === "FAILURE" ? "failed" : task.state === "SUCCESS" ? "indexed" : "indexing");
    const indexed = ["indexed", "ready"].includes(String(nextIndexStatus).toLowerCase());
    setDocuments((current) =>
      current.map((document) => {
        if (document.doc_id !== docId) {
          return document;
        }

        return {
          ...document,
          status: task.state === "FAILURE" ? "failed" : document.status || "uploaded",
          index_status: nextIndexStatus,
          progress: indexed ? 100 : task.progress,
          chunks: chunkCount ?? document.chunks,
          vectorized: indexed,
          error: task.error,
          updated_at: nowIso(),
        };
      }),
    );
  }

  async function pollTask(
    taskId: string,
    defaults: Partial<TaskRecord>,
    onUpdate: (task: TaskStatus) => void,
  ): Promise<TaskStatus> {
    for (let round = 0; round < POLL_MAX_ROUNDS; round += 1) {
      const task = await getTaskStatus(apiBaseUrl, taskId);
      upsertTaskRecord(task, defaults);
      onUpdate(task);

      if (task.state === "SUCCESS") {
        return task;
      }
      if (task.state === "FAILURE" || task.state === "FAILED") {
        throw new Error(task.error || "任务执行失败");
      }

      await sleep(POLL_INTERVAL_MS);
    }

    throw new Error("轮询超时，请检查后端任务队列是否正常");
  }

  async function refreshHealth(silent = false) {
    if (!silent) {
      setRefreshingHealth(true);
      setPending("health");
    }

    const startedAt = performance.now();
    try {
      const nextHealth = await getHealth(apiBaseUrl);
      const latency = Math.max(1, Math.round(performance.now() - startedAt));
      setHealth(nextHealth);
      setApiLatencyMs(latency);
      setError(null);
      recordMetricPoint(buildFallbackOverview(nextHealth, taskRecords, documents, latency, topK));
    } catch (nextError) {
      if (!silent) {
        setError(nextError instanceof Error ? nextError.message : "健康检查失败");
      }
    } finally {
      if (!silent) {
        setPending(null);
        setRefreshingHealth(false);
      }
    }
  }

  async function refreshUsers(silent = false) {
    try {
      const users = await listLatestUsers(apiBaseUrl, 8);
      setLatestUsers(users);
      if (!userId && users[0]) {
        setUserId(String(users[0].id));
      }
    } catch (nextError) {
      if (!silent) {
        setError(nextError instanceof Error ? nextError.message : "刷新用户失败");
      }
    }
  }

  async function refreshDocuments(silent = false) {
    try {
      const items = await listDocuments(apiBaseUrl, 200);
      setDocuments((current) =>
        items.map((item) => {
          const local = current.find((document) => document.doc_id === item.doc_id);
          return {
            ...item,
            progress: local?.progress ?? (isIndexedDocument(item) ? 100 : 0),
            task_id: local?.task_id,
            error: item.error || item.error_message || local?.error || null,
          };
        }),
      );
      setCurrentDocumentId((current) => current ?? items[0]?.doc_id ?? null);
    } catch (nextError) {
      if (!silent) {
        setError(nextError instanceof Error ? nextError.message : "刷新文档库失败");
      }
    }
  }

  async function handleCreateUser() {
    const trimmedName = newUserName.trim();
    if (!trimmedName) {
      setError("请输入用户名");
      return;
    }

    setPending("user");
    setError(null);
    try {
      const user = await createUser(apiBaseUrl, trimmedName);
      setUserId(String(user.id));
      setNewUserName("");
      setLatestUsers((current) => [user, ...current.filter((item) => item.id !== user.id)].slice(0, 8));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "创建用户失败");
    } finally {
      setPending(null);
    }
  }

  function handleSelectUser(user: UserItem) {
    setUserId(String(user.id));
  }

  async function handleCreateSession() {
    setPending("session");
    setError(null);
    try {
      const parsedUserId = parsePositiveInteger(userId, "User ID");
      const title = `RAG Session ${sessions.length + 1}`;
      const nextSession = await createSession(apiBaseUrl, parsedUserId, title);
      setSession(nextSession);
      setSessions((current) => [
        {
          session_id: nextSession.session_id,
          title: nextSession.title,
          updated_at: nextSession.updated_at || nextSession.created_at,
          message_count: 0,
          status: "active",
        },
        ...current.map((item) => ({ ...item, status: "idle" as const })),
      ]);
      setMessagesBySession((current) => ({ ...current, [nextSession.session_id]: [] }));
      setAgentTraceRows([]);
      navigate("workspace");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "创建会话失败");
    } finally {
      setPending(null);
    }
  }

  function handleSelectSession(sessionId: number) {
    const summary = sessions.find((item) => item.session_id === sessionId);
    if (!summary) {
      return;
    }
    setSession({
      session_id: summary.session_id,
      user_id: Number(userId) || 1,
      title: summary.title,
      created_at: summary.updated_at || nowIso(),
      updated_at: summary.updated_at || undefined,
    });
    setSessions((current) =>
      current.map((item) => ({ ...item, status: item.session_id === sessionId ? "active" : "idle" })),
    );
    setAgentTraceRows([]);
    navigate("workspace");
  }

  async function handleRefreshMessages() {
    if (!session) {
      setError("请先创建会话");
      return;
    }

    setPending("messages");
    setError(null);
    try {
      const messages = await listMessages(apiBaseUrl, session.session_id);
      setMessagesForSession(session.session_id, messages);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "刷新消息失败");
    } finally {
      setPending(null);
    }
  }

  async function handleUploadDocument() {
    if (!selectedFile) {
      setError("请先选择文件");
      return;
    }
    if (!SUPPORTED_DOCUMENT_RE.test(selectedFile.name)) {
      setError("当前仅支持 .md、.txt、.json、.csv、.pdf、.docx、.xlsx 文件");
      return;
    }

    setPending("upload");
    setError(null);
    setIngestTask(null);
    try {
      const parsedUserId = parsePositiveInteger(userId, "User ID");
      const uploadResult = await uploadDocument(apiBaseUrl, parsedUserId, selectedFile);
      const taskDefaults = registerPendingDocument(uploadResult);
      await waitForDocumentIngest(uploadResult, taskDefaults);
      setSelectedFile(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "上传失败");
    } finally {
      setPending(null);
    }
  }

  function registerPendingDocument(uploadResult: UploadDocumentResponse): Partial<TaskRecord> {
    const createdAt = nowIso();
    const documentItem: DocumentListItem = {
      doc_id: uploadResult.doc_id,
      filename: uploadResult.filename,
      status: "uploaded",
      index_status: "not_indexed",
      chunks: null,
      vectorized: false,
      created_at: createdAt,
      updated_at: createdAt,
      task_id: uploadResult.task_id,
      progress: 0,
    };
    const taskDefaults: Partial<TaskRecord> = {
      type: "parse_document",
      entity_type: "document",
      entity_id: uploadResult.doc_id,
      db_task_id: uploadResult.db_task_id,
      created_at: createdAt,
    };

    setDocuments((current) => [documentItem, ...current.filter((document) => document.doc_id !== uploadResult.doc_id)]);
    setCurrentDocumentId(uploadResult.doc_id);
    upsertTaskRecord(
      {
        task_id: uploadResult.task_id,
        state: uploadResult.state || "PENDING",
        progress: 0,
        meta: { stage: "queued", doc_id: uploadResult.doc_id, filename: uploadResult.filename },
        error: null,
      },
      taskDefaults,
    );
    setSelectedTaskId(uploadResult.task_id);
    return taskDefaults;
  }

  async function waitForDocumentIngest(uploadResult: UploadDocumentResponse, taskDefaults: Partial<TaskRecord>) {
    const finalTask = await pollTask(uploadResult.task_id, taskDefaults, (task) => {
      setIngestTask(task);
      updateDocumentFromTask(uploadResult.doc_id, task);
    });
    updateDocumentFromTask(uploadResult.doc_id, finalTask);
    await refreshDocuments(true);
  }

  async function handleUploadWebDocument() {
    const trimmedUrl = webUrl.trim();
    if (!trimmedUrl) {
      setError("请输入网页 URL");
      return;
    }

    let parsedUrl: URL;
    try {
      parsedUrl = new URL(trimmedUrl);
    } catch {
      setError("网页 URL 格式不正确");
      return;
    }
    if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") {
      setError("网页 URL 必须以 http:// 或 https:// 开头");
      return;
    }

    setPending("web-upload");
    setError(null);
    setIngestTask(null);
    try {
      const parsedUserId = parsePositiveInteger(userId, "User ID");
      const uploadResult = await uploadWebDocument(apiBaseUrl, parsedUserId, trimmedUrl);
      const taskDefaults = registerPendingDocument(uploadResult);
      await waitForDocumentIngest(uploadResult, taskDefaults);
      setWebUrl("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "网页导入失败");
    } finally {
      setPending(null);
    }
  }

  async function handleDeleteDocument(docId: number) {
    const target = documents.find((document) => document.doc_id === docId);
    const label = target?.filename || `doc ${docId}`;
    if (!window.confirm(`删除 ${label}？这会同步删除数据库记录、chunk 和 LanceDB 索引。`)) {
      return;
    }

    setPending(`delete-document-${docId}`);
    setError(null);
    try {
      await deleteDocument(apiBaseUrl, docId);
      setDocuments((current) => current.filter((document) => document.doc_id !== docId));
      setTaskRecords((current) => current.filter((task) => !(task.entity_type === "document" && task.entity_id === docId)));
      if (currentDocumentId === docId) {
        const nextDocument = documents.find((document) => document.doc_id !== docId) || null;
        setCurrentDocumentId(nextDocument?.doc_id ?? null);
      }
      await refreshDocuments(true);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "删除文档失败");
    } finally {
      setPending(null);
    }
  }

  async function handleAsk() {
    if (!session) {
      setError("请先创建会话");
      return;
    }
    if (readyDocuments.length === 0) {
      setError("请先上传文档并等待 index_status indexed 后再提问");
      return;
    }
    const prompt = question.trim();
    if (!prompt) {
      setError("请输入问题");
      return;
    }

    setPending("chat");
    setError(null);
    setChatTask(null);
    setQuestion("");
    const readyDocIds = readyDocuments.map((document) => document.doc_id);
    let streamTaskId: string | null = null;
    try {
      if (streamingEnabled) {
        const useAgentStream = ragEnabled;
        const userMessage = buildLocalMessage(session.session_id, "user", prompt, "SUCCESS");
        const assistantMessage = buildLocalMessage(session.session_id, "assistant", "", "PROCESSING");
        streamTaskId = `stream-${Date.now()}`;
        if (useAgentStream) {
          startAgentTrace(prompt);
        } else {
          setAgentTraceRows([]);
        }
        let queuedDelta = "";
        let animationFrame: number | null = null;
        const flushDelta = () => {
          const nextDelta = queuedDelta;
          queuedDelta = "";
          animationFrame = null;
          if (!nextDelta) {
            return;
          }
          updateMessagesForSession(session.session_id, (messages) =>
            messages.map((message) =>
              message.message_id === assistantMessage.message_id
                ? {
                    ...message,
                    content: message.content + nextDelta,
                    updated_at: nowIso(),
                    status: "PROCESSING",
                  }
                : message,
            ),
          );
        };
        const queueDelta = (delta: string) => {
          queuedDelta += delta;
          if (animationFrame === null) {
            animationFrame = window.requestAnimationFrame(flushDelta);
          }
        };

        updateMessagesForSession(session.session_id, (messages) => [
          ...messages,
          userMessage,
          assistantMessage,
        ]);
        setChatTask({
          task_id: streamTaskId,
          state: "PROCESSING",
          progress: 50,
          meta: {
            stage: useAgentStream ? "agent_streaming" : "streaming",
            session_id: session.session_id,
            doc_ids: readyDocIds,
          },
          error: null,
        });
        setSelectedTaskId(streamTaskId);

        try {
          const callbacks: StreamChatCallbacks = {
            onDelta: (delta: string) => {
              if (!delta) {
                return;
              }
              queueDelta(delta);
            },
            onDone: (meta: StreamChatDoneMeta) => {
              if (animationFrame !== null) {
                window.cancelAnimationFrame(animationFrame);
              }
              flushDelta();
              updateMessagesForSession(session.session_id, (messages) =>
                messages.map((message) =>
                  message.message_id === assistantMessage.message_id
                    ? {
                        ...message,
                        status: "SUCCESS",
                        updated_at: nowIso(),
                        meta: {
                          ...message.meta,
                          agent_run_id: meta.agent_run_id,
                          answer_source: meta.answer_source || (useAgentStream ? "agent" : undefined),
                          context_mode: meta.context_mode,
                          retrieved_count: meta.retrieved_count,
                          citation_count: meta.citation_count,
                          doc_ids: meta.doc_ids || readyDocIds,
                          retrieval_ms: meta.retrieval_ms,
                          lancedb_ms: meta.lancedb_ms,
                          rerank_ms: meta.rerank_ms,
                          raw_hit_count: meta.raw_hit_count,
                          ttft_ms: meta.ttft_ms,
                          e2e_latency_ms: meta.e2e_latency_ms,
                          steps_used: meta.steps_used,
                        },
                      }
                    : message,
                ),
              );
              setChatTask({
                task_id: streamTaskId || `stream-${Date.now()}`,
                state: "SUCCESS",
                progress: 100,
                meta: {
                  stage: useAgentStream ? "agent_finished" : "finished",
                  session_id: session.session_id,
                  doc_ids: meta.doc_ids || readyDocIds,
                  agent_run_id: meta.agent_run_id,
                  answer_source: meta.answer_source || (useAgentStream ? "agent" : undefined),
                  context_mode: meta.context_mode,
                  retrieved_count: meta.retrieved_count,
                  citation_count: meta.citation_count,
                  retrieval_ms: meta.retrieval_ms,
                  lancedb_ms: meta.lancedb_ms,
                  rerank_ms: meta.rerank_ms,
                  raw_hit_count: meta.raw_hit_count,
                  ttft_ms: meta.ttft_ms,
                  e2e_latency_ms: meta.e2e_latency_ms,
                  prompt_tokens: meta.prompt_tokens,
                  completion_tokens: meta.completion_tokens,
                  cost_usd: meta.cost_usd,
                  no_context: meta.no_context,
                  steps_used: meta.steps_used,
                },
                error: null,
              });
            },
            onAgentStep: (event: AgentStepEvent) => handleAgentStepEvent(event, prompt),
            onToolCall: handleAgentToolCallEvent,
            onToolResult: handleAgentToolResultEvent,
            onFinal: (event: AgentFinalEvent) => {
              handleAgentFinalEvent(event);
              const citations = normalizeCitations(event.citations);
              if (citations.length === 0) {
                return;
              }
              updateMessagesForSession(session.session_id, (messages) =>
                messages.map((message) =>
                  message.message_id === assistantMessage.message_id
                    ? { ...message, citations, updated_at: nowIso() }
                    : message,
                ),
              );
            },
          };

          if (useAgentStream) {
            await streamAgentChat(
              apiBaseUrl,
              {
                session_id: session.session_id,
                message: prompt,
              },
              callbacks,
            );
          } else {
            await streamChat(
              apiBaseUrl,
              {
                session_id: session.session_id,
                content: prompt,
                top_k: topK,
              },
              callbacks,
            );
          }
        } finally {
          if (animationFrame !== null) {
            window.cancelAnimationFrame(animationFrame);
            flushDelta();
          }
        }

        try {
          const messages = await listMessages(apiBaseUrl, session.session_id);
          setMessagesForSession(session.session_id, messages);
        } catch (refreshError) {
          setError(
            refreshError instanceof Error
              ? `流式回答已完成，但刷新消息失败: ${refreshError.message}`
              : "流式回答已完成，但刷新消息失败",
          );
        }
        return;
      }

      const submitted = await submitChat(
        apiBaseUrl,
        session.session_id,
        prompt,
        topK,
      );
      const taskDefaults: Partial<TaskRecord> = {
        type: "chat_generate",
        entity_type: "session",
        entity_id: session.session_id,
        db_task_id: submitted.db_task_id,
        created_at: nowIso(),
      };
      upsertTaskRecord(
        {
          task_id: submitted.task_id,
          state: submitted.state,
          progress: 0,
          meta: {
            stage: "queued",
            session_id: session.session_id,
            doc_ids: readyDocIds,
            user_message_id: submitted.message_id,
          },
          error: null,
        },
        taskDefaults,
      );
      setSelectedTaskId(submitted.task_id);

      await pollTask(submitted.task_id, taskDefaults, setChatTask);
      const messages = await listMessages(apiBaseUrl, session.session_id);
      setMessagesForSession(session.session_id, messages);
    } catch (nextError) {
      if (streamingEnabled) {
        updateMessagesForSession(session.session_id, (messages) =>
          messages.map((message, index) =>
            index === messages.length - 1 && message.role === "assistant"
              ? { ...message, status: "FAILURE", updated_at: nowIso() }
              : message,
          ),
        );
        setChatTask({
          task_id: streamTaskId || `stream-${Date.now()}`,
          state: "FAILURE",
          progress: 100,
          meta: {
            stage: "failed",
            session_id: session.session_id,
            doc_ids: readyDocIds,
          },
          error: nextError instanceof Error ? nextError.message : "流式提问失败",
        });
      }
      setError(nextError instanceof Error ? nextError.message : "提问失败");
      setQuestion((current) => current || prompt);
    } finally {
      setPending(null);
    }
  }

  async function refreshKnownTasks() {
    const activeTasks = taskRecords.filter((task) => !isTerminalTask(task.state));
    if (activeTasks.length === 0) {
      return;
    }

    await Promise.all(
      activeTasks.map(async (task) => {
        try {
          const status = await getTaskStatus(apiBaseUrl, task.task_id);
          upsertTaskRecord(status, task);
          if (task.entity_type === "document") {
            updateDocumentFromTask(task.entity_id, status);
          }
          if (task.task_id === ingestTask?.task_id) {
            setIngestTask(status);
          }
          if (task.task_id === chatTask?.task_id) {
            setChatTask(status);
          }
        } catch {
          // Keep the last known state. The detail panel still shows the previous task state.
        }
      }),
    );
  }

  async function handleRefreshTasks() {
    setTaskListError(null);
    try {
      const remoteTasks = await listTasks(apiBaseUrl, 50);
      setTaskRecords((current) => {
        const merged = [...remoteTasks];
        current.forEach((task) => {
          if (!merged.some((item) => item.task_id === task.task_id)) {
            merged.push(task);
          }
        });
        return merged;
      });
    } catch {
      setTaskListError("任务列表暂不可用，已保留本地任务状态。");
    }
    await refreshKnownTasks();
  }

  async function handleRefreshMonitor() {
    try {
      const nextOverview = await getMonitorOverview(apiBaseUrl);
      const normalized: MonitorOverview = {
        ...nextOverview,
        source: "monitor-api",
      };
      setMonitorOverview(normalized);
      setMonitorError(null);
      recordMetricPoint(normalized);
    } catch {
      setMonitorOverview(null);
      setMonitorError("监控数据暂不可用，已显示基础健康状态。");
    }
  }

  function renderRoute() {
    if (route === "documents") {
      return (
        <DocumentsPage
          documents={documents}
          selectedDocId={currentDocumentId}
          tasks={taskRecords}
          selectedFileName={selectedFileName}
          webUrl={webUrl}
          pending={pending}
          onSelectDocument={setCurrentDocumentId}
          onFileChange={setSelectedFile}
          onWebUrlChange={setWebUrl}
          onUpload={handleUploadDocument}
          onUploadWebDocument={handleUploadWebDocument}
          onDeleteDocument={handleDeleteDocument}
        />
      );
    }

    if (route === "tasks") {
      return (
        <TasksPage
          tasks={taskRecords}
          selectedTaskId={selectedTaskId}
          taskListError={taskListError}
          onSelectTask={setSelectedTaskId}
          onRefreshTasks={handleRefreshTasks}
        />
      );
    }

    if (route === "monitor") {
      return (
        <MonitorPage
          overview={overview}
          points={metricPoints.length > 0 ? metricPoints : [{ label: "now", api_ms: apiLatencyMs }]}
          monitorError={monitorError}
          onRefreshMonitor={handleRefreshMonitor}
        />
      );
    }

    if (route === "settings") {
      return (
        <SettingsPage
          apiBaseUrl={apiBaseUrl}
          userId={userId}
          topK={topK}
          ragEnabled={ragEnabled}
          streamingEnabled={streamingEnabled}
          chunkSize={chunkSize}
          chunkOverlap={chunkOverlap}
          modelName={modelName}
          onApiBaseUrlChange={setApiBaseUrl}
          onUserIdChange={setUserId}
          onTopKChange={setTopK}
          onRagEnabledChange={setRagEnabled}
          onStreamingEnabledChange={setStreamingEnabled}
          onChunkSizeChange={setChunkSize}
          onChunkOverlapChange={setChunkOverlap}
          onModelNameChange={setModelName}
        />
      );
    }

    return (
      <WorkspacePage
        session={session}
        readyDocumentCount={readyDocuments.length}
        messages={currentMessages}
        question={question}
        topK={topK}
        ragEnabled={ragEnabled}
        streamingEnabled={streamingEnabled}
        pending={pending}
        selectedFileName={selectedFileName}
        error={error}
        ingestTask={ingestTask}
        chatTask={chatTask}
        agentTraceRows={agentTraceRows}
        onCreateSession={handleCreateSession}
        onRefreshMessages={handleRefreshMessages}
        onQuestionChange={setQuestion}
        onTopKChange={setTopK}
        onRagEnabledChange={setRagEnabled}
        onFileChange={setSelectedFile}
        onUpload={handleUploadDocument}
        onAsk={handleAsk}
      />
    );
  }

  useEffect(() => {
    void refreshUsers(true);
    void refreshDocuments(true);
    // This effect is intentionally keyed only by API base URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBaseUrl]);

  usePolling(() => refreshHealth(true), route === "monitor" ? 2000 : 5000, true);
  usePolling(() => refreshKnownTasks(), 3000, route === "tasks" || route === "monitor");
  usePolling(() => handleRefreshMonitor(), 2000, route === "monitor");

  return (
    <AppShell
      route={route}
      overview={overview}
      searchScope={`Global KB · ${readyDocuments.length} ready docs`}
      sessions={sessions}
      currentSessionId={session?.session_id || null}
      users={latestUsers}
      userId={userId}
      newUserName={newUserName}
      pending={pending}
      refreshing={refreshingHealth}
      retrievalMode={ragEnabled ? `RAG top_${topK}` : "Direct"}
      modelName={modelName}
      onNavigate={navigate}
      onRefresh={() => void refreshHealth(false)}
      onSelectSession={handleSelectSession}
      onNewSession={handleCreateSession}
      onSelectUser={handleSelectUser}
      onNewUserNameChange={setNewUserName}
      onCreateUser={handleCreateUser}
    >
      {renderRoute()}
    </AppShell>
  );
}
