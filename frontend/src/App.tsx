import { FormEvent, useEffect, useState } from "react";

import {
  createSession,
  createUser,
  getHealth,
  getTaskStatus,
  listLatestUsers,
  listMessages,
  submitChat,
  uploadDocument,
} from "./api/client";
import type { HealthSnapshot } from "./types/api";
import type { UploadDocumentResponse } from "./types/document";
import type { ChatMessage } from "./types/message";
import type { Session } from "./types/session";
import type { TaskStatus } from "./types/task";
import type { UserItem } from "./types/user";

type TimelineItem = {
  id: number;
  text: string;
};

const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "";

const POLL_INTERVAL_MS = 1500;
const POLL_MAX_ROUNDS = 80;

function nowLabel(): string {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function formatTaskStage(task: TaskStatus | null): string {
  if (!task) {
    return "未开始";
  }
  const stage = typeof task.meta?.stage === "string" ? task.meta.stage : "处理中";
  return `${task.state} · ${stage} · ${task.progress}%`;
}

function formatScore(score: number): string {
  return Number.isFinite(score) ? score.toFixed(3) : "-";
}

function formatDocumentStatus(documentInfo: UploadDocumentResponse | null, ingestTask: TaskStatus | null): string {
  if (!documentInfo) {
    return "未上传";
  }
  if (!ingestTask) {
    return "已上传";
  }
  if (ingestTask.state === "SUCCESS") {
    return "已就绪";
  }
  if (ingestTask.state === "FAILURE") {
    return "索引失败";
  }
  return "索引中";
}

function parsePositiveInteger(value: string, fieldName: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${fieldName} 必须是正整数`);
  }
  return parsed;
}

export default function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [userId, setUserId] = useState("1");
  const [newUserName, setNewUserName] = useState("");
  const [sessionTitle, setSessionTitle] = useState("Demo Session");
  const [question, setQuestion] = useState("这份文档讲了什么？");
  const [topK, setTopK] = useState("3");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [latestUsers, setLatestUsers] = useState<UserItem[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [documentInfo, setDocumentInfo] = useState<UploadDocumentResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [ingestTask, setIngestTask] = useState<TaskStatus | null>(null);
  const [chatTask, setChatTask] = useState<TaskStatus | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [usersLoading, setUsersLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);

  function appendTimeline(text: string) {
    setTimeline((current) => [
      { id: Date.now() + current.length, text: `${nowLabel()} ${text}` },
      ...current,
    ]);
  }

  async function pollTask(taskId: string, onUpdate: (task: TaskStatus) => void): Promise<TaskStatus> {
    for (let round = 0; round < POLL_MAX_ROUNDS; round += 1) {
      const task = await getTaskStatus(apiBaseUrl, taskId);
      onUpdate(task);

      if (task.state === "SUCCESS") {
        return task;
      }
      if (task.state === "FAILURE") {
        throw new Error(task.error || "任务执行失败");
      }

      await sleep(POLL_INTERVAL_MS);
    }

    throw new Error("轮询超时，请检查后端任务队列是否正常");
  }

  async function refreshUsers(silent = false) {
    setUsersLoading(true);
    try {
      const nextUsers = await listLatestUsers(apiBaseUrl, 6);
      setLatestUsers(nextUsers);
      if (!silent) {
        appendTimeline(`最近用户已刷新，共 ${nextUsers.length} 条`);
      }
    } catch (nextError) {
      if (!silent) {
        const message = nextError instanceof Error ? nextError.message : "刷新用户失败";
        setError(message);
        appendTimeline(`刷新用户失败：${message}`);
      }
    } finally {
      setUsersLoading(false);
    }
  }

  async function handleHealthCheck() {
    setPending("health");
    setError(null);
    try {
      const nextHealth = await getHealth(apiBaseUrl);
      setHealth(nextHealth);
      appendTimeline(`健康检查完成，网关状态：${nextHealth.ok ? "正常" : "异常"}`);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "健康检查失败";
      setError(message);
      appendTimeline(`健康检查失败：${message}`);
    } finally {
      setPending(null);
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
      const createdUser = await createUser(apiBaseUrl, trimmedName);
      setUserId(String(createdUser.id));
      setNewUserName("");
      setLatestUsers((current) => [createdUser, ...current.filter((item) => item.id !== createdUser.id)].slice(0, 6));
      appendTimeline(`已创建用户：user_id=${createdUser.id}，name=${createdUser.name}`);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "创建用户失败";
      setError(message);
      appendTimeline(`创建用户失败：${message}`);
    } finally {
      setPending(null);
    }
  }

  function handleSelectUser(user: UserItem) {
    setUserId(String(user.id));
    appendTimeline(`已切换用户：user_id=${user.id}，name=${user.name}`);
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!selectedFile) {
      setError("请先选择文件");
      return;
    }

    if (!/\.(md|txt|json|csv|pdf|docx)$/i.test(selectedFile.name)) {
      setError("当前仅支持 .md、.txt、.json、.csv、.pdf、.docx 文件");
      return;
    }

    setPending("upload");
    setError(null);
    setIngestTask(null);

    try {
      const parsedUserId = parsePositiveInteger(userId, "User ID");
      const uploadResult = await uploadDocument(apiBaseUrl, parsedUserId, selectedFile);
      setDocumentInfo(uploadResult);
      appendTimeline(`文档已上传：doc_id=${uploadResult.doc_id}，开始轮询 ingest 任务`);

      const finalTask = await pollTask(uploadResult.task_id, setIngestTask);
      appendTimeline(`文档索引完成：state=${finalTask.state}`);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "上传失败";
      setError(message);
      appendTimeline(`上传或 ingest 失败：${message}`);
    } finally {
      setPending(null);
    }
  }

  async function handleCreateSession() {
    setPending("session");
    setError(null);
    try {
      const parsedUserId = parsePositiveInteger(userId, "User ID");
      const nextSession = await createSession(apiBaseUrl, parsedUserId, sessionTitle.trim() || "Demo Session");
      setSession(nextSession);
      appendTimeline(`已创建会话：session_id=${nextSession.session_id}`);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "创建会话失败";
      setError(message);
      appendTimeline(`创建会话失败：${message}`);
    } finally {
      setPending(null);
    }
  }

  async function handleAsk() {
    if (!session) {
      setError("请先创建会话");
      return;
    }
    if (!documentInfo) {
      setError("请先上传并完成索引");
      return;
    }
    if (ingestTask?.state !== "SUCCESS") {
      setError("文档索引尚未完成，请等待 ingest 成功");
      return;
    }

    setPending("chat");
    setError(null);
    setChatTask(null);

    try {
      const parsedTopK = parsePositiveInteger(topK, "Top K");
      const submitted = await submitChat(
        apiBaseUrl,
        session.session_id,
        documentInfo.doc_id,
        question.trim(),
        parsedTopK,
      );
      appendTimeline(`问题已提交：message_id=${submitted.message_id}，开始轮询 chat 任务`);

      const finalTask = await pollTask(submitted.task_id, setChatTask);
      appendTimeline(`回答生成完成：assistant_message_id=${String(finalTask.meta?.assistant_message_id ?? "-")}`);

      const nextMessages = await listMessages(apiBaseUrl, session.session_id);
      setMessages(nextMessages);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "提问失败";
      setError(message);
      appendTimeline(`提问失败：${message}`);
    } finally {
      setPending(null);
    }
  }

  async function handleRefreshMessages() {
    if (!session) {
      setError("请先创建会话");
      return;
    }

    setPending("messages");
    setError(null);

    try {
      const nextMessages = await listMessages(apiBaseUrl, session.session_id);
      setMessages(nextMessages);
      appendTimeline(`消息列表已刷新，共 ${nextMessages.length} 条`);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "刷新消息失败";
      setError(message);
      appendTimeline(`刷新消息失败：${message}`);
    } finally {
      setPending(null);
    }
  }

  useEffect(() => {
    void handleHealthCheck();
    void refreshUsers(true);
  }, []);

  const documentReady = ingestTask?.state === "SUCCESS";
  const documentStatus = formatDocumentStatus(documentInfo, ingestTask);
  const nextAction = !documentInfo
    ? "先上传文档并等待索引完成。"
    : !documentReady
      ? "文档已上传，正在等待索引完成。"
      : !session
      ? "文档已就绪，下一步创建会话。"
      : "会话和文档都已准备好，可以直接提问。";

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">RAG Demo Console</p>
          <h1>整理后的最小演示前端</h1>
          <p className="hero-copy">
            这个页面直接串联网关能力：健康检查、文档上传、索引任务轮询、会话创建、提问和消息回放。
          </p>
        </div>
        <div className="hero-status">
          <span className={`status-pill ${health?.ok ? "status-ok" : "status-warn"}`}>
            {health?.ok ? "Gateway Healthy" : "Need Attention"}
          </span>
          <p>{nextAction}</p>
        </div>
      </header>

      <main className="workspace">
        <section className="panel panel-form">
          <div className="panel-head">
            <h2>连接与流程</h2>
            <button type="button" onClick={handleHealthCheck} disabled={pending !== null}>
              {pending === "health" ? "检查中..." : "重新检查"}
            </button>
          </div>

          <label className="field">
            <span>Gateway Base URL</span>
            <input
              value={apiBaseUrl}
              onChange={(event) => setApiBaseUrl(event.target.value)}
              placeholder="留空则走 Vite 代理，直连时可填 http://server-ip:8080"
            />
          </label>

          <form
            className="stack"
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreateUser();
            }}
          >
            <div className="panel-head panel-head-compact">
              <h3>用户</h3>
              <button
                type="button"
                className="button-secondary"
                onClick={() => void refreshUsers()}
                disabled={pending !== null || usersLoading}
              >
                {usersLoading ? "刷新中..." : "刷新用户"}
              </button>
            </div>
            <label className="field">
              <span>新用户名称</span>
              <input
                value={newUserName}
                onChange={(event) => setNewUserName(event.target.value)}
                placeholder="例如 demo_user_01"
              />
            </label>
            <button type="submit" disabled={pending !== null}>
              {pending === "user" ? "创建中..." : "创建用户"}
            </button>
            {latestUsers.length === 0 ? (
              <p className="muted">暂无最近用户，先创建一个。</p>
            ) : (
              <div className="user-chip-list">
                {latestUsers.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`user-chip ${userId === String(item.id) ? "user-chip-active" : ""}`}
                    onClick={() => handleSelectUser(item)}
                    disabled={pending !== null}
                  >
                    <strong>{item.name}</strong>
                    <span>#{item.id}</span>
                  </button>
                ))}
              </div>
            )}
          </form>

          <div className="field-row">
            <label className="field">
              <span>当前 User ID</span>
              <input value={userId} onChange={(event) => setUserId(event.target.value)} />
            </label>
            <label className="field">
              <span>Top K</span>
              <input value={topK} onChange={(event) => setTopK(event.target.value)} />
            </label>
          </div>

          <form className="stack" onSubmit={handleUpload}>
            <label className="field">
              <span>选择演示文档</span>
              <input
                type="file"
                accept=".md,.txt,.json,.csv,.pdf,.docx"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <small className="field-hint">
              当前支持 `.md`、`.txt`、`.json`、`.csv`、`.pdf`、`.docx`。PDF 仅支持可提取文本的电子版，扫描件暂不支持 OCR。
            </small>
            <button type="submit" disabled={pending !== null}>
              {pending === "upload" ? "上传并轮询中..." : "1. 上传并建立索引"}
            </button>
          </form>

          <div className="stack">
            <label className="field">
              <span>会话标题</span>
              <input value={sessionTitle} onChange={(event) => setSessionTitle(event.target.value)} />
            </label>
            <button type="button" onClick={handleCreateSession} disabled={pending !== null}>
              {pending === "session" ? "创建中..." : "2. 创建会话"}
            </button>
          </div>

          <div className="stack">
            <label className="field">
              <span>问题</span>
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={4} />
            </label>
            <div className="button-row">
              <button type="button" onClick={handleAsk} disabled={pending !== null}>
                {pending === "chat" ? "提问中..." : "3. 提问并轮询回答"}
              </button>
              <button type="button" className="button-secondary" onClick={handleRefreshMessages} disabled={pending !== null}>
                {pending === "messages" ? "刷新中..." : "刷新消息"}
              </button>
            </div>
          </div>

          {error ? <p className="error-box">{error}</p> : null}
        </section>

        <section className="panel panel-state">
          <div className="panel-head">
            <h2>系统状态</h2>
          </div>

          <div className="health-grid">
            <article className="stat-card">
              <span>Gateway</span>
              <strong>{health?.ok ? "OK" : "Unknown"}</strong>
            </article>
            <article className="stat-card">
              <span>MySQL</span>
              <strong>{health?.mysql?.ok ? "OK" : "Check"}</strong>
            </article>
            <article className="stat-card">
              <span>Redis</span>
              <strong>{health?.redis?.ok ? "OK" : "Check"}</strong>
            </article>
            <article className="stat-card">
              <span>Python</span>
              <strong>{health?.python?.ok ? "OK" : "Check"}</strong>
            </article>
          </div>

          <div className="info-grid">
            <article className="info-card">
              <span>Document</span>
              <strong>{documentInfo ? `#${documentInfo.doc_id} · ${documentStatus}` : "未上传"}</strong>
              <p>{documentInfo?.filename || "等待文件"}</p>
              <small>{formatTaskStage(ingestTask)}</small>
            </article>
            <article className="info-card">
              <span>Session</span>
              <strong>{session ? `#${session.session_id}` : "未创建"}</strong>
              <p>{session?.title || "等待会话"}</p>
            </article>
            <article className="info-card">
              <span>Chat Task</span>
              <strong>{chatTask?.state || "未开始"}</strong>
              <p>{typeof chatTask?.meta?.answer_source === "string" ? String(chatTask.meta.answer_source) : "等待回答"}</p>
              <small>{formatTaskStage(chatTask)}</small>
            </article>
          </div>

          <div className="timeline">
            <div className="panel-head">
              <h3>执行时间线</h3>
            </div>
            {timeline.length === 0 ? (
              <p className="muted">暂无记录。</p>
            ) : (
              <ul>
                {timeline.map((item) => (
                  <li key={item.id}>{item.text}</li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </main>

      <section className="panel panel-chat">
        <div className="panel-head">
          <h2>消息回放</h2>
          <p>这里展示网关最终读到的消息列表和 citations。</p>
        </div>

        {messages.length === 0 ? (
          <p className="muted">当前没有消息。先完成会话创建并提问。</p>
        ) : (
          <div className="message-list">
            {messages.map((message) => (
              <article key={message.message_id} className={`message-card role-${message.role}`}>
                <div className="message-head">
                  <span>{message.role}</span>
                  <small>{message.created_at}</small>
                </div>
                <p>{message.content}</p>
                <div className="message-meta">
                  <span>status: {message.status}</span>
                  <span>citations: {message.citations.length}</span>
                </div>
                {message.citations.length > 0 ? (
                  <div className="citation-list">
                    {message.citations.map((citation, index) => (
                      <div key={`${message.message_id}-${citation.chunk_id}-${index}`} className="citation-card">
                        <strong>
                          doc #{citation.doc_id} · chunk #{citation.chunk_index}
                        </strong>
                        <span>score {formatScore(citation.score)}</span>
                        <p>{citation.snippet}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
