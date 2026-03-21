"use client";

import { useState } from "react";

interface AgentChatPanelProps {
  appName: string;
}

export default function AgentChatPanel({ appName }: AgentChatPanelProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: input }]);
    // Mock agent response
    setMessages((prev) => [
      ...prev,
      { role: "agent", content: `[${appName}] Processing: "${input}"...` },
    ]);
    setInput("");
  };

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="fixed bottom-4 right-4 z-50 w-12 h-12 rounded-full flex items-center justify-center shadow-lg"
        style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}
        aria-label="Open Agent Chat"
      >
        💬
      </button>
    );
  }

  return (
    <div
      className="fixed bottom-4 right-4 z-50 w-96 rounded-lg border shadow-xl flex flex-col"
      style={{
        height: 480,
        backgroundColor: "var(--background-card)",
        borderColor: "var(--border)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Agent Chat
          </span>
          <span
            className="text-xs px-2 py-0.5 rounded"
            style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}
          >
            Sonnet
          </span>
        </div>
        <button
          onClick={() => setCollapsed(true)}
          className="text-sm"
          style={{ color: "var(--text-muted)" }}
          aria-label="Close chat"
        >
          ✕
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Ask the {appName} agent anything...
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className="text-sm rounded-lg px-3 py-2"
            style={{
              backgroundColor: msg.role === "user" ? "var(--brand-glow)" : "var(--background-hover)",
              color: "var(--text-primary)",
            }}
          >
            {msg.content}
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="p-3 border-t" style={{ borderColor: "var(--border)" }}>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type a message..."
            className="flex-1 text-sm px-3 py-2 rounded border outline-none"
            style={{
              backgroundColor: "var(--background)",
              borderColor: "var(--border)",
              color: "var(--text-primary)",
            }}
          />
          <button
            onClick={handleSend}
            className="px-3 py-2 rounded text-sm font-medium"
            style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
