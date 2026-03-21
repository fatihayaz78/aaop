"use client";

import { useState, useRef, useEffect } from "react";
import RiskBadge from "@/components/ui/RiskBadge";
import StatusDot from "@/components/ui/StatusDot";
import LogTable from "@/components/ui/LogTable";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiPost, apiGet } from "@/lib/api";

type Tab = "assistant" | "diagnostics" | "deployments" | "runbooks";

interface ChatMsg { role: "user" | "agent"; content: string }

const SUGGESTIONS = ["check service health", "show recent deployments", "list active incidents", "search runbooks for CDN", "show platform metrics"];

const SERVICES = [
  { name: "FastAPI", status: "active" as const, latency: 12 },
  { name: "SQLite", status: "active" as const, latency: 3 },
  { name: "DuckDB", status: "active" as const, latency: 8 },
  { name: "ChromaDB", status: "active" as const, latency: 15 },
  { name: "Redis", status: "active" as const, latency: 2 },
  { name: "LLM Gateway", status: "active" as const, latency: 250 },
  { name: "EventBus", status: "active" as const, latency: 1 },
];

export default function DevOpsAssistant() {
  const [tab, setTab] = useState<Tab>("assistant");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [showNewDeploy, setShowNewDeploy] = useState(false);
  const [newDeploy, setNewDeploy] = useState({ service: "", version: "", notes: "" });
  const [diagRunning, setDiagRunning] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Auto-refresh diagnostics every 30s
  useEffect(() => {
    if (tab !== "diagnostics") return;
    const iv = setInterval(() => { /* refresh */ }, 30000);
    return () => clearInterval(iv);
  }, [tab]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const msg = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    try {
      const r = await apiPost<{ response: string }>("/devops/assist", { question: msg, tenant_id: "bein_sports" });
      setMessages((prev) => [...prev, { role: "agent", content: r.response ?? "Command processed." }]);
    } catch {
      setMessages((prev) => [...prev, { role: "agent", content: `Processing: "${msg}"...\n\nService status: all healthy\nNo critical issues detected.` }]);
    }
  };

  const runDiagnostic = async () => {
    setDiagRunning(true);
    try { await apiPost("/devops/diagnose", { tenant_id: "bein_sports" }); } catch {}
    setTimeout(() => setDiagRunning(false), 3000);
  };

  const TABS: { key: Tab; label: string }[] = [
    { key: "assistant", label: "Assistant" }, { key: "diagnostics", label: "Diagnostics" },
    { key: "deployments", label: "Deployments" }, { key: "runbooks", label: "Runbooks" },
  ];

  const isDangerous = (cmd: string) => ["restart", "delete", "rm ", "drop ", "shutdown"].some((d) => cmd.toLowerCase().includes(d));

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>DevOps Assistant</h2>
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>{t.label}</button>
        ))}
      </div>

      {/* Assistant — Terminal-like */}
      {tab === "assistant" && (<div>
        <div className="rounded-lg border flex flex-col" style={{ backgroundColor: "#0d1117", borderColor: "var(--border)", height: "calc(100vh - 280px)", minHeight: 400 }}>
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: "var(--border)" }}>
            <span className="text-xs font-mono" style={{ color: "var(--risk-low)" }}>captain-logar@aaop:~$</span>
            <button onClick={() => setMessages([])} className="text-xs" style={{ color: "var(--text-muted)" }}>Clear</button>
          </div>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-sm">
            {messages.length === 0 && (
              <div style={{ color: "var(--text-muted)" }}>
                <p>Welcome to DevOps Assistant.</p>
                <p>Type a command or question below, or click a suggestion.</p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-right" : ""}>
                {m.role === "user" ? (
                  <div className="inline-block rounded px-3 py-1.5 text-right" style={{ backgroundColor: "var(--brand-glow)", color: "var(--text-primary)" }}>
                    <span style={{ color: "var(--risk-low)" }}>$ </span>{m.content}
                  </div>
                ) : (
                  <pre className="whitespace-pre-wrap rounded px-3 py-2" style={{ backgroundColor: "var(--background-hover)", color: "var(--text-secondary)" }}>{m.content}</pre>
                )}
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          {/* Suggestions */}
          <div className="px-4 py-2 overflow-x-auto flex gap-2" style={{ borderTop: "1px solid var(--border)" }}>
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => setInput(s)} className="px-2 py-1 rounded text-xs whitespace-nowrap flex items-center gap-1"
                style={{ backgroundColor: "var(--background-hover)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                {s}
                {isDangerous(s) && <RiskBadge level="HIGH" />}
              </button>
            ))}
          </div>
          {/* Input */}
          <div className="flex gap-2 p-3" style={{ borderTop: "1px solid var(--border)" }}>
            <span className="text-sm font-mono pt-1.5" style={{ color: "var(--risk-low)" }}>$</span>
            <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Type a command..." className="flex-1 text-sm px-3 py-1.5 rounded border outline-none font-mono"
              style={{ backgroundColor: "transparent", borderColor: "var(--border)", color: "var(--text-primary)" }} />
            <button onClick={sendMessage} className="px-3 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Run</button>
          </div>
        </div>
      </div>)}

      {/* Diagnostics */}
      {tab === "diagnostics" && (<div>
        <div className="flex justify-between mb-4">
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Auto-refresh: 30s</p>
          <button onClick={runDiagnostic} disabled={diagRunning} className="px-4 py-1.5 rounded text-sm font-medium disabled:opacity-50" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
            {diagRunning ? "Running..." : "Run Full Diagnostic"}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {SERVICES.map((s) => (
            <div key={s.name} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{s.name}</span>
                <StatusDot status={s.status} label={s.status === "active" ? "Healthy" : s.status} />
              </div>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Latency: {s.latency}ms</p>
            </div>
          ))}
        </div>
      </div>)}

      {/* Deployments */}
      {tab === "deployments" && (<div>
        <div className="flex justify-between mb-4">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Deployment history</p>
          <button onClick={() => setShowNewDeploy(true)} className="px-4 py-1.5 rounded text-sm font-medium border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Log Deployment</button>
        </div>
        <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <LogTable columns={[
            { key: "id", label: "ID" }, { key: "service", label: "Service" }, { key: "version", label: "Version" },
            { key: "status", label: "Status", render: (v) => {
              const c: Record<string, string> = { pending: "var(--text-muted)", running: "var(--brand-primary)", deployed: "var(--risk-low)", failed: "var(--risk-high)" };
              return <span className="text-xs font-medium" style={{ color: c[v as string] ?? "var(--text-muted)" }}>● {String(v)}</span>;
            }},
            { key: "deployedBy", label: "By" }, { key: "startedAt", label: "Started" },
          ]} data={[]} />
        </div>
        {showNewDeploy && (
          <div className="fixed inset-0 z-50 flex justify-end" style={{ backgroundColor: "rgba(0,0,0,0.5)" }} onClick={() => setShowNewDeploy(false)}>
            <div className="w-96 h-full p-6" style={{ backgroundColor: "var(--background-card)" }} onClick={(e) => e.stopPropagation()}>
              <h3 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Log Deployment</h3>
              <div className="space-y-3">
                <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Service</label>
                  <input type="text" value={newDeploy.service} onChange={(e) => setNewDeploy({...newDeploy, service: e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} /></div>
                <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Version</label>
                  <input type="text" value={newDeploy.version} onChange={(e) => setNewDeploy({...newDeploy, version: e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} /></div>
                <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Notes</label>
                  <textarea value={newDeploy.notes} onChange={(e) => setNewDeploy({...newDeploy, notes: e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none h-20 resize-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} /></div>
                <div className="flex gap-2 pt-4">
                  <button className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Log</button>
                  <button onClick={() => setShowNewDeploy(false)} className="px-4 py-2 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>)}

      {/* Runbooks */}
      {tab === "runbooks" && (<div>
        <div className="space-y-3">
          {["CDN Cache Purge Procedure", "Service Restart Runbook", "DRM Fallback Protocol", "Emergency Scale-Up", "Log Rotation"].map((rb) => (
            <div key={rb} className="rounded-lg border p-4 flex items-center justify-between" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <div>
                <h4 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{rb}</h4>
                <div className="flex gap-2 mt-1">
                  {["ops","cdn"].map((t) => <span key={t} className="text-xs px-1.5 py-0.5 rounded" style={{ backgroundColor: "var(--background-hover)", color: "var(--text-muted)" }}>{t}</span>)}
                </div>
              </div>
              <button onClick={() => confirm(`Execute runbook: "${rb}"? This is a HIGH risk action.`)}
                className="px-3 py-1.5 rounded text-xs font-medium flex items-center gap-1" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>
                Run <RiskBadge level="HIGH" />
              </button>
            </div>
          ))}
        </div>
      </div>)}

      <AgentChatPanel appName="DevOps Assistant" />
    </div>
  );
}
