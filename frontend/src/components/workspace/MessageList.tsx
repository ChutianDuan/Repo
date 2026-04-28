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
        description="上传文档并创建会话后即可提问。"
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
