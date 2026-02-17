import { useState, useRef, useEffect } from "react";
import type { ChatMessage } from "../../types";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (message: string) => void;
  onSearchReady: () => void;
  isLoading: boolean;
  isReadyToSearch: boolean;
}

const ChatPanel = ({
  messages,
  onSend,
  onSearchReady,
  isLoading,
  isReadyToSearch,
}: ChatPanelProps) => {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <div
      style={{
        backgroundColor: "#fff",
        borderRadius: 12,
        padding: 24,
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
        display: "flex",
        flexDirection: "column",
        height: 500,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h2 style={{ margin: 0 }}>Refine Your Search</h2>
        <button
          onClick={onSearchReady}
          style={{
            padding: "8px 20px",
            backgroundColor: isReadyToSearch ? "#16a34a" : "#6b7280",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: "0.875rem",
          }}
        >
          Start Search
        </button>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 12,
          padding: "8px 0",
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: "#9ca3af", textAlign: "center", marginTop: 40 }}>
            Tell me more about what you're looking for -- color, features, fuel
            type, anything!
          </p>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{
              alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
              backgroundColor: msg.role === "user" ? "#1a1a2e" : "#f0f0f0",
              color: msg.role === "user" ? "#fff" : "#1a1a1a",
              padding: "10px 16px",
              borderRadius: 12,
              maxWidth: "75%",
              fontSize: "0.95rem",
              lineHeight: 1.5,
            }}
          >
            {msg.content}
          </div>
        ))}

        {isLoading && (
          <div
            style={{
              alignSelf: "flex-start",
              color: "#9ca3af",
              fontStyle: "italic",
            }}
          >
            Thinking...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", gap: 8, marginTop: 12 }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. I prefer white or silver, must have sunroof..."
          style={{
            flex: 1,
            padding: "10px 14px",
            borderRadius: 8,
            border: "1px solid #d1d5db",
            fontSize: "0.95rem",
          }}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          style={{
            padding: "10px 20px",
            backgroundColor: "#1a1a2e",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            cursor: "pointer",
            opacity: isLoading || !input.trim() ? 0.5 : 1,
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatPanel;
