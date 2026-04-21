import type { ChatMessage } from "../../types/message";
import { EmptyState } from "../common/EmptyState";
import { MessageBubble } from "./MessageBubble";

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <EmptyState
        title="还没有问答记录"
        description="先上传并索引一份文档，然后创建会话发起第一个问题。"
      />
    );
  }

  return (
    <div className="message-list">
      {messages.map((message) => (
        <MessageBubble key={message.message_id} message={message} />
      ))}
    </div>
  );
}
