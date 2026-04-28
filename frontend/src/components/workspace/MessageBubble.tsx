import type { ChatMessage } from "../../types/message";
import { StatusBadge } from "../common/StatusBadge";
import { TimestampText } from "../common/TimestampText";
import { formatScore, stateTone } from "../../utils/format";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isStreaming = message.role === "assistant" && message.status === "PROCESSING";

  return (
    <article className={`message-bubble message-bubble--${message.role}`}>
      <div className="message-bubble__head">
        <div>
          <span>{message.role === "user" ? "Question" : "Answer"}</span>
          <TimestampText value={message.created_at} />
        </div>
        <StatusBadge label={message.status} tone={stateTone(message.status)} />
      </div>
      <p className={isStreaming ? "message-bubble__content message-bubble__content--streaming" : "message-bubble__content"}>
        {message.content || (isStreaming ? "正在生成" : "")}
        {isStreaming ? <span className="stream-cursor" aria-hidden="true" /> : null}
      </p>
      {message.citations.length > 0 ? (
        <div className="inline-citations">
          {message.citations.slice(0, 4).map((citation, index) => (
            <span key={`${message.message_id}-${citation.chunk_id}-${index}`}>
              doc {citation.doc_id} · chunk {citation.chunk_index} · {formatScore(citation.score)}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}
