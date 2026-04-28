import { useEffect, useState } from "react";

import { useHashRoute } from "./router";
import { AppShell } from "../components/layout/AppShell";
import { DocumentsPage } from "../pages/documents/DocumentsPage";
import { MonitorPage } from "../pages/monitor/MonitorPage";
import { SettingsPage } from "../pages/settings/SettingsPage";
import { TasksPage } from "../pages/tasks/TasksPage";
import { WorkspacePage } from "../pages/workspace/WorkspacePage";
import { createSession, listMessages, streamChat, submitChat } from "../services/chatService";
import { uploadDocument } from "../services/documentService";
import { getHealth, getMonitorOverview } from "../services/monitorService";
import { getTaskStatus, listTasks } from "../services/taskService";
import { createUser, listLatestUsers } from "../services/userService";
import { usePolling } from "../hooks/usePolling";
import type { HealthSnapshot } from "../types/api";
import type { DocumentListItem } from "../types/document";
import type { ChatMessage } from "../types/message";
import type { MetricPoint, MonitorOverview, ServiceState } from "../types/monitor";
import type { Session, SessionSummary } from "../types/session";
import type { TaskRecord, TaskStatus } from "../types/task";
import type { UserItem } from "../types/user";
import { nowIso } from "../utils/format";

const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.trim() || "";
const POLL_INTERVAL_MS = 1500;
const POLL_MAX_ROUNDS = 80;
const SUPPORTED_DOCUMENT_RE = /\.(md|txt|json|csv|pdf|docx)$/i;

type PendingAction =
  | "health"
  | "user"
  | "upload"
  | "session"
  | "chat"
  | "messages"
  | null;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function parsePositiveInteger(value: string, fieldName: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${fieldName} 必须是正整数`);
  }
  return parsed;
}

function normalizeTopK(value: number): number {
  if (!Number.isFinite(value)) {
    return 3;
  }
  return Math.max(1, Math.min(20, Math.round(value)));
}

function serviceState(ok: boolean | undefined): ServiceState {
  if (ok === true) {
    return "ok";
  }
  if (ok === false) {
    return "error";
  }
  return "unknown";
}

function isTerminalTask(state: string): boolean {
  return ["SUCCESS", "FAILURE", "FAILED"].includes(state);
}

function getChunkCount(meta: Record<string, unknown> | null | undefined): number | null {
  const value = meta?.chunk_count;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function buildFallbackOverview(
  health: HealthSnapshot | null,
  tasks: TaskRecord[],
  documents: DocumentListItem[],
  apiLatencyMs: number | null,
  topK: number,
): MonitorOverview {
  const pending = tasks.filter((task) => task.state === "PENDING").length;
  const running = tasks.filter((task) => !isTerminalTask(task.state) && task.state !== "PENDING").length;
  const failed = tasks.filter((task) => task.state === "FAILURE" || task.state === "FAILED").length;
  const readyDocuments = documents.filter((document) => document.status === "READY");
  const knownChunks = readyDocuments
    .map((document) => document.chunks)
    .filter((value): value is number => typeof value === "number");

  return {
    system: {
      cpu_percent: null,
      memory_percent: null,
      memory_used_gb: null,
      memory_total_gb: null,
      disk_percent: null,
    },
    gpu: [],
    services: {
      mysql: serviceState(health?.mysql?.ok),
      redis: serviceState(health?.redis?.ok),
      worker: tasks.length > 0 ? "ok" : "unknown",
      llm: "unknown",
      embedding: "unknown",
      api: serviceState(health?.ok),
    },
    queue: {
      pending,
      running,
      failed,
      worker_count: null,
      worker_concurrency_configured: null,
      worker_concurrency_observed: null,
    },
    latency: {
      api_ms: apiLatencyMs,
      ttft_ms: null,
      chat_ms: null,
      response_ms: null,
      retrieval_ms: null,
      faiss_ms: null,
      ingest_ms: null,
      document_parse_ms: null,
    },
    rag: {
      documents_ready: readyDocuments.length,
      total_chunks: knownChunks.length > 0 ? knownChunks.reduce((sum, value) => sum + value, 0) : null,
      max_document_size_bytes: null,
      top_k: topK,
      retrieval_mode: "document",
    },
    ingest: {
      document_parse_ms: {},
      chunk_count: {},
    },
    experience: {
      ttft_ms: {},
      e2e_latency_ms: {},
      ingest_ready_ms: {},
    },
    cost: {
      prompt_tokens_avg: null,
      prompt_tokens_total: null,
      completion_tokens_avg: null,
      completion_tokens_total: null,
      cost_per_request_usd: null,
      cost_per_document_usd: null,
      chat_cost_total_usd: null,
      ingest_cost_total_usd: null,
    },
    throughput: {
      qps: null,
      concurrent_sessions: null,
      worker_queue_depth: pending + running,
      active_sse_connections: null,
      celery_concurrency_configured: null,
      celery_concurrency_observed: null,
      celery_pool: null,
    },
    quality: {
      retrieval_ms: {},
      faiss_ms: {},
      error_rate: null,
      timeout_rate: null,
      citation_count_avg: null,
      no_context_ratio: null,
      retrieval_eval_samples: null,
      recall_at_k_avg: null,
      mrr_avg: null,
      ndcg_avg: null,
    },
    samples: {
      total: tasks.length,
      chat: null,
      ingest: null,
    },
    updated_at: nowIso(),
    source: "health-fallback",
  };
}

function taskRecordFromStatus(
  status: TaskStatus,
  existing: TaskRecord | undefined,
  defaults: Partial<TaskRecord>,
): TaskRecord {
  return {
    task_id: status.task_id,
    type: defaults.type || existing?.type || "system",
    entity_type: defaults.entity_type || existing?.entity_type || "system",
    entity_id: defaults.entity_id ?? existing?.entity_id ?? 0,
    db_task_id: defaults.db_task_id ?? existing?.db_task_id,
    state: status.state,
    progress: status.progress,
    meta: status.meta ?? null,
    error: status.error ?? null,
    created_at: existing?.created_at || defaults.created_at || nowIso(),
    updated_at: nowIso(),
  };
}

function buildLocalMessage(
  sessionId: number,
  role: ChatMessage["role"],
  content: string,
  status: string,
): ChatMessage {
  const timestamp = nowIso();
  return {
    message_id: -Math.floor(Date.now() + Math.random() * 1000000),
    session_id: sessionId,
    role,
    content,
    status,
    citations: [],
    meta: {},
    created_at: timestamp,
    updated_at: timestamp,
  };
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
  const [monitorOverview, setMonitorOverview] = useState<MonitorOverview | null>(null);
  const [metricPoints, setMetricPoints] = useState<MetricPoint[]>([]);
  const [pending, setPending] = useState<PendingAction>(null);
  const [refreshingHealth, setRefreshingHealth] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taskListError, setTaskListError] = useState<string | null>(null);
  const [monitorError, setMonitorError] = useState<string | null>(null);

  const currentMessages = session ? messagesBySession[session.session_id] || [] : [];
  const currentDocument = documents.find((document) => document.doc_id === currentDocumentId) || null;
  const overview = monitorOverview || buildFallbackOverview(health, taskRecords, documents, apiLatencyMs, topK);
  const selectedFileName = selectedFile?.name || null;

  function setTopK(value: number) {
    setTopKState(normalizeTopK(value));
  }

  function recordMetricPoint(nextOverview: MonitorOverview) {
    const timestamp = new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    setMetricPoints((current) => [
      ...current.slice(-17),
      {
        label: timestamp,
        cpu: nextOverview.system.cpu_percent,
        gpu: nextOverview.gpu[0]?.util_percent ?? null,
        api_ms: nextOverview.latency.api_ms,
        throughput: nextOverview.throughput.qps ?? taskRecords.filter((task) => task.state === "SUCCESS").length,
      },
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

  function updateDocumentFromTask(docId: number, task: TaskStatus) {
    const chunkCount = getChunkCount(task.meta);
    setDocuments((current) =>
      current.map((document) => {
        if (document.doc_id !== docId) {
          return document;
        }

        return {
          ...document,
          status: task.state === "SUCCESS" ? "READY" : task.state === "FAILURE" ? "FAILED" : "PROCESSING",
          progress: task.progress,
          chunks: chunkCount ?? document.chunks,
          vectorized: task.state === "SUCCESS",
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
      setError("当前仅支持 .md、.txt、.json、.csv、.pdf、.docx 文件");
      return;
    }

    setPending("upload");
    setError(null);
    setIngestTask(null);
    try {
      const parsedUserId = parsePositiveInteger(userId, "User ID");
      const uploadResult = await uploadDocument(apiBaseUrl, parsedUserId, selectedFile);
      const createdAt = nowIso();
      const documentItem: DocumentListItem = {
        doc_id: uploadResult.doc_id,
        filename: uploadResult.filename,
        status: "PROCESSING",
        chunks: null,
        vectorized: false,
        created_at: createdAt,
        updated_at: createdAt,
        task_id: uploadResult.task_id,
        progress: 0,
      };
      const taskDefaults: Partial<TaskRecord> = {
        type: "ingest_document",
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

      const finalTask = await pollTask(uploadResult.task_id, taskDefaults, (task) => {
        setIngestTask(task);
        updateDocumentFromTask(uploadResult.doc_id, task);
      });
      updateDocumentFromTask(uploadResult.doc_id, finalTask);
      setSelectedFile(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "上传失败");
    } finally {
      setPending(null);
    }
  }

  async function handleAsk() {
    if (!session) {
      setError("请先创建会话");
      return;
    }
    if (!currentDocument) {
      setError("请先上传并选择文档");
      return;
    }
    if (currentDocument.status !== "READY") {
      setError("文档索引尚未完成，请等待 READY 后再提问");
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
    let streamTaskId: string | null = null;
    try {
      if (streamingEnabled) {
        const userMessage = buildLocalMessage(session.session_id, "user", prompt, "SUCCESS");
        const assistantMessage = buildLocalMessage(session.session_id, "assistant", "", "PROCESSING");
        streamTaskId = `stream-${Date.now()}`;
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
            stage: "streaming",
            session_id: session.session_id,
            doc_id: currentDocument.doc_id,
          },
          error: null,
        });
        setSelectedTaskId(streamTaskId);

        try {
          await streamChat(
            apiBaseUrl,
            {
              session_id: session.session_id,
              doc_id: currentDocument.doc_id,
              content: prompt,
              top_k: topK,
            },
            {
              onDelta: (delta) => {
                if (!delta) {
                  return;
                }
                queueDelta(delta);
              },
              onDone: (meta) => {
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
                            answer_source: meta.answer_source,
                            context_mode: meta.context_mode,
                            retrieved_count: meta.retrieved_count,
                            citation_count: meta.citation_count,
                            retrieval_ms: meta.retrieval_ms,
                            ttft_ms: meta.ttft_ms,
                            e2e_latency_ms: meta.e2e_latency_ms,
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
                    stage: "finished",
                    session_id: session.session_id,
                    doc_id: currentDocument.doc_id,
                    answer_source: meta.answer_source,
                    context_mode: meta.context_mode,
                    retrieved_count: meta.retrieved_count,
                    citation_count: meta.citation_count,
                    retrieval_ms: meta.retrieval_ms,
                    ttft_ms: meta.ttft_ms,
                    e2e_latency_ms: meta.e2e_latency_ms,
                    prompt_tokens: meta.prompt_tokens,
                    completion_tokens: meta.completion_tokens,
                    cost_usd: meta.cost_usd,
                    no_context: meta.no_context,
                  },
                  error: null,
                });
              },
            },
          );
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
        currentDocument.doc_id,
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
            doc_id: currentDocument.doc_id,
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
            doc_id: currentDocument.doc_id,
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
          pending={pending}
          onSelectDocument={setCurrentDocumentId}
          onFileChange={setSelectedFile}
          onUpload={handleUploadDocument}
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
        currentDocument={currentDocument}
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
  }, [apiBaseUrl]);

  usePolling(() => refreshHealth(true), route === "monitor" ? 2000 : 5000, true);
  usePolling(() => refreshKnownTasks(), 3000, route === "tasks" || route === "monitor");
  usePolling(() => handleRefreshMonitor(), 2000, route === "monitor");

  return (
    <AppShell
      route={route}
      overview={overview}
      searchScope={currentDocument ? currentDocument.filename : "No document selected"}
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
