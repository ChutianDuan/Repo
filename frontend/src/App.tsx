import { FormEvent, useEffect, useState } from "react";

import { createSession, getHealth, getTaskStatus, listMessages, submitChat, uploadDocument } from "./api/client";
import type { HealthSnapshot } from "./types/api";
import type { UploadDocumentResponse } from "./types/document";
import type { ChatMessage } from "./types/message";
import type { Session } from "./types/session";
import type { TaskStatus } from "./types/task";

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

export default function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [userId, setUserId] = useState("1");
  const [sessionTitle, setSessionTitle] = useState("Demo Session");
  const [question, setQuestion] = useState("这份文档讲了什么？");
  const [topK, setTopK] = useState("3");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [documentInfo, setDocumentInfo] = useState<UploadDocumentResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [ingestTask, setIngestTask] = useState<TaskStatus | null>(null);
  const [chatTask, setChatTask] = useState<TaskStatus | null>(null);
  const [pending, setPending] = useState<string | null>(null);
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

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!selectedFile) {
      setError("请先选择文件");
      return;
    }

    setPending("upload");
    setError(null);
    setIngestTask(null);

    try {
      const uploadResult = await uploadDocument(apiBaseUrl, Number(userId), selectedFile);
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
      const nextSession = await createSession(apiBaseUrl, Number(userId), sessionTitle.trim() || "Demo Session");
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

    setPending("chat");
    setError(null);
    setChatTask(null);

    try {
      const submitted = await submitChat(
        apiBaseUrl,
        session.session_id,
        documentInfo.doc_id,
        question.trim(),
        Number(topK),
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
  }, []);

  const nextAction = !documentInfo
    ? "先上传文档并等待索引完成。"
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

          <div className="field-row">
            <label className="field">
              <span>User ID</span>
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
                accept=".md,.txt,.json,.pdf"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
            </label>
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
              <strong>{documentInfo ? `#${documentInfo.doc_id}` : "未上传"}</strong>
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
