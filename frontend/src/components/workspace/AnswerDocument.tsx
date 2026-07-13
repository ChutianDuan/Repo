import { ArrowRight, ArrowsClockwise, Plus, Quotes } from "@phosphor-icons/react";
import type { ReactNode } from "react";
import type { Citation } from "../../types/citation";
import type { ChatMessage } from "../../types/message";
import type { Session, SessionSummary } from "../../types/session";

interface AnswerDocumentProps {
  session: Session | null;
  sessions: SessionSummary[];
  userMessage: ChatMessage | null;
  assistantMessage: ChatMessage | null;
  question: string;
  topK: number;
  ragEnabled: boolean;
  streamingEnabled: boolean;
  pending: string | null;
  error: string | null;
  documentNames: Map<number, string>;
  hoveredCitation: Citation | null;
  onCitationHover: (citation: Citation | null) => void;
  onCreateSession: () => void;
  onSelectSession: (sessionId: number) => void;
  onRefreshMessages: () => void;
  onQuestionChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onRagEnabledChange: (value: boolean) => void;
  onAsk: () => void;
}

function answerWithCitationMarkers(
  content: string,
  citations: Citation[],
  onCitationHover: (citation: Citation | null) => void,
): { body: ReactNode; hasInlineMarkers: boolean } {
  const markerPattern = /\[(\d+)\]/g;
  const matches = [...content.matchAll(markerPattern)];
  if (matches.length === 0) {
    return { body: content, hasInlineMarkers: false };
  }

  const parts: ReactNode[] = [];
  let cursor = 0;
  matches.forEach((match, index) => {
    const start = match.index ?? cursor;
    if (start > cursor) parts.push(content.slice(cursor, start));
    const citationIndex = Number(match[1]) - 1;
    const citation = citations[citationIndex];
    if (citation) {
      parts.push(
        <button
          type="button"
          className="citation-marker"
          data-citation-doc-id={citation.doc_id}
          key={`${match[0]}-${index}`}
          onMouseEnter={() => onCitationHover(citation)}
          onMouseLeave={() => onCitationHover(null)}
          onFocus={() => onCitationHover(citation)}
          onBlur={() => onCitationHover(null)}
          title={`doc ${citation.doc_id}, chunk ${citation.chunk_index}`}
        >
          {match[0]}
        </button>,
      );
    } else {
      parts.push(match[0]);
    }
    cursor = start + match[0].length;
  });
  if (cursor < content.length) parts.push(content.slice(cursor));
  return { body: parts, hasInlineMarkers: true };
}

export function AnswerDocument({
  session,
  sessions,
  userMessage,
  assistantMessage,
  question,
  topK,
  ragEnabled,
  streamingEnabled,
  pending,
  error,
  documentNames,
  hoveredCitation,
  onCitationHover,
  onCreateSession,
  onSelectSession,
  onRefreshMessages,
  onQuestionChange,
  onTopKChange,
  onRagEnabledChange,
  onAsk,
}: AnswerDocumentProps) {
  const isStreaming = pending === "chat" || assistantMessage?.status === "PROCESSING";
  const citations = assistantMessage?.citations || [];
  const answer = assistantMessage?.content?.trim() || "";
  const renderedAnswer = answerWithCitationMarkers(answer, citations, onCitationHover);
  const displayedQuestion = userMessage?.content || question || "根据知识库总结这个系统的文档入库和 Agent 问答链路";

  return (
    <section className="answer-document" aria-labelledby="answer-document-title">
      <header className="answer-document__session">
        <div>
          <span>Current session</span>
          {sessions.length > 0 ? (
            <select
              value={session?.session_id || ""}
              onChange={(event) => onSelectSession(Number(event.target.value))}
              aria-label="Current session"
            >
              {!session ? <option value="">Select a session</option> : null}
              {sessions.map((item) => (
                <option key={item.session_id} value={item.session_id}>{item.title}</option>
              ))}
            </select>
          ) : (
            <strong>No session created</strong>
          )}
        </div>
        <div className="answer-document__session-actions">
          <button type="button" onClick={onRefreshMessages} disabled={!session || pending !== null} title="Refresh messages">
            <ArrowsClockwise size={16} />
          </button>
          <button type="button" onClick={onCreateSession} disabled={pending !== null}>
            <Plus size={15} />
            {session ? "New session" : "Create session"}
          </button>
        </div>
      </header>

      <article className="answer-reader">
        <div className="answer-reader__question">
          <span>User question</span>
          <h2 id="answer-document-title">{displayedQuestion}</h2>
        </div>

        <div className="answer-reader__body">
          <div className="answer-reader__label">
            <Quotes size={18} />
            <span>{isStreaming ? "Answer stream" : "Answer"}</span>
            {streamingEnabled ? <code>SSE</code> : null}
          </div>
          {answer ? (
            <p>
              {renderedAnswer.body}
              {isStreaming ? <span className="stream-cursor" aria-hidden="true" /> : null}
            </p>
          ) : (
            <p className="answer-reader__empty">
              提交问题后，回答会按 SSE 增量写入这里；完成后再显示已保存的 citations。
            </p>
          )}

          {citations.length > 0 && !renderedAnswer.hasInlineMarkers ? (
            <div className="answer-evidence-band">
              <span>本次检索证据</span>
              <div>
                {citations.map((citation, index) => (
                  <button
                    type="button"
                    className={hoveredCitation?.chunk_id === citation.chunk_id ? "citation-marker is-active" : "citation-marker"}
                    data-citation-doc-id={citation.doc_id}
                    key={`${citation.doc_id}-${citation.chunk_id}-${index}`}
                    onMouseEnter={() => onCitationHover(citation)}
                    onMouseLeave={() => onCitationHover(null)}
                    onFocus={() => onCitationHover(citation)}
                    onBlur={() => onCitationHover(null)}
                    title={`${documentNames.get(citation.doc_id) || `doc ${citation.doc_id}`} / chunk ${citation.chunk_index}`}
                  >
                    [{index + 1}]
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {hoveredCitation ? (
            <div className="active-evidence">
              <strong>{documentNames.get(hoveredCitation.doc_id) || `doc ${hoveredCitation.doc_id}`}</strong>
              <code>chunk {hoveredCitation.chunk_index}</code>
              <p>{hoveredCitation.snippet || "Citation snippet is not available."}</p>
            </div>
          ) : null}
        </div>
      </article>

      {error ? <div className="workbench-inline-error">{error}</div> : null}

      <form
        className="answer-composer"
        onSubmit={(event) => {
          event.preventDefault();
          onAsk();
        }}
      >
        <textarea
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="输入需要由知识库回答的问题"
          rows={2}
          disabled={isStreaming}
          aria-label="Question"
        />
        <div className="answer-composer__controls">
          <label>
            <input
              type="checkbox"
              checked={ragEnabled}
              onChange={(event) => onRagEnabledChange(event.target.checked)}
            />
            <span>{ragEnabled ? "Agent + RAG" : "Direct"}</span>
          </label>
          <label>
            <span>topK</span>
            <input
              type="number"
              min={1}
              max={10}
              value={topK}
              onChange={(event) => onTopKChange(Number(event.target.value))}
            />
          </label>
          <button type="submit" disabled={!session || pending !== null || !question.trim()}>
            {isStreaming ? "Streaming" : "Run query"}
            <ArrowRight size={16} />
          </button>
        </div>
      </form>
    </section>
  );
}
