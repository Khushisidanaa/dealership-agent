import { useState, useEffect, useRef } from "react";
import { api } from "../api/client";
import type { ChatMessage } from "../types";
import "./ChatWindow.css";

interface ChatWindowProps {
  sessionId: string;
  onChatReply: (
    updatedFilters?: Record<string, unknown>,
    readyToSearch?: boolean,
  ) => void;
  requirementsComplete: boolean;
  onGoToDashboard: () => void;
}

export function ChatWindow({
  sessionId,
  onChatReply,
  requirementsComplete,
  onGoToDashboard,
}: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const adjustInputHeight = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    api.chat.history(sessionId).then((r) => setMessages(r.messages));
  }, [sessionId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    adjustInputHeight();
  }, [input]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text, timestamp: new Date().toISOString() },
    ]);
    setSending(true);
    try {
      const res = await api.chat.send(sessionId, text);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          timestamp: new Date().toISOString(),
        },
      ]);
      onChatReply(res.updated_filters ?? undefined, res.is_ready_to_search);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="chat-window">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <p>
              Tell me what you’re looking for: budget, body type, brand,
              distance, and any must-haves.
            </p>
            <p>
              I’ll fill in your requirements and when we’re ready, you can open
              the Dashboard to see matching dealerships and cars.
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-message chat-message--${m.role}`}>
            <div className="chat-message-bubble">{m.content}</div>
          </div>
        ))}
        {sending && (
          <div className="chat-message chat-message--assistant">
            <div className="chat-message-bubble chat-message-bubble--typing">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-actions">
        {requirementsComplete && (
          <button
            type="button"
            className="chat-action-dashboard"
            onClick={onGoToDashboard}
          >
            Search & Call Dealers
          </button>
        )}
      </div>

      <div className="chat-input-row">
        <textarea
          ref={inputRef}
          className="chat-input chat-input--textarea"
          placeholder="Type your message…"
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            adjustInputHeight();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={sending}
          rows={1}
        />
        <button
          type="button"
          className="chat-send"
          onClick={send}
          disabled={sending || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
