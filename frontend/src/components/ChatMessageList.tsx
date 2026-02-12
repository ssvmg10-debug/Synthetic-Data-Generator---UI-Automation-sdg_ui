import React, { useEffect, useRef } from "react";
import type { ChatMessage } from "./AgentChat";

interface ChatMessageListProps {
  messages: ChatMessage[];
  renderPayload: (message: ChatMessage) => React.ReactNode;
}

export const ChatMessageList: React.FC<ChatMessageListProps> = ({
  messages,
  renderPayload
}) => {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-list">
      {messages.map(msg => (
        <div
          key={msg.id}
          className={
            "chat-message " + (msg.sender === "user" ? "chat-message-user" : "chat-message-agent")
          }
        >
          <div className="chat-avatar">
            {msg.sender === "user" ? "You" : "Agent"}
          </div>
          <div className="chat-bubble">
            <div className="chat-text">{msg.text}</div>
            {renderPayload(msg) && (
              <div className="chat-payload">{renderPayload(msg)}</div>
            )}
            <div className="chat-meta">
              <span>
                {new Date(msg.createdAt).toLocaleTimeString(undefined, {
                  hour: "2-digit",
                  minute: "2-digit"
                })}
              </span>
            </div>
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
};

