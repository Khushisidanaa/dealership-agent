import { useState, useEffect, useRef } from "react";
import { api } from "../api/client";
import type { ChatMessage } from "../types";
import type { Phase } from "../App";
import "./ChatSidebar.css";

interface ChatSidebarProps {
  sessionId: string;
  userName: string;
  onChatReply: (
    updatedFilters?: Record<string, unknown>,
    readyToSearch?: boolean,
  ) => void;
  requirementsComplete: boolean;
  onGoToResults: () => void;
  currentPhase: Phase;
  isOpen: boolean;
  onToggle: () => void;
}

export function ChatSidebar({
  sessionId,
  userName,
  onChatReply,
  requirementsComplete,
  onGoToResults,
  currentPhase,
  isOpen,
  onToggle,
}: ChatSidebarProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.chat.history(sessionId).then((r) => setMessages(r.messages));
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Something went wrong. Try again.",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <aside
      className={`chat-sidebar ${isOpen ? "" : "chat-sidebar--collapsed"}`}
    >
      <div className="chat-sidebar-header">
        <h3>Chat</h3>
        <button
          type="button"
          className="chat-sidebar-toggle"
          onClick={onToggle}
          title={isOpen ? "Collapse chat" : "Expand chat"}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {isOpen ? (
              <polyline points="15 18 9 12 15 6" />
            ) : (
              <polyline points="9 18 15 12 9 6" />
            )}
          </svg>
        </button>
        {requirementsComplete &&
          (currentPhase === "chat" || currentPhase === "results") && (
            <button
              type="button"
              className="chat-sidebar-cta"
              onClick={onGoToResults}
            >
              {currentPhase === "chat" ? "View Results" : "Refresh Results"}
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
          )}
      </div>

      <div className="chat-sidebar-messages">
        {messages.length === 0 && (
          <div className="chat-sidebar-empty">
            <p>Hi {userName}! Tell me what kind of car you are looking for.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`cs-msg cs-msg--${m.role}`}>
            <div className="cs-msg-bubble">{m.content}</div>
          </div>
        ))}
        {sending && (
          <div className="cs-msg cs-msg--assistant">
            <div className="cs-msg-bubble cs-msg-typing">
              <span className="cs-dot" />
              <span className="cs-dot" />
              <span className="cs-dot" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-sidebar-input">
        <textarea
          ref={inputRef}
          className="cs-input"
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
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
          className="cs-send"
          onClick={send}
          disabled={sending || !input.trim()}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
