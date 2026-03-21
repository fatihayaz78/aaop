"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import SeverityBadge from "@/components/ui/SeverityBadge";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet } from "@/lib/api";
import type { SeverityLevel } from "@/types";

type Tab = "dashboard" | "sessions" | "anomalies" | "complaints" | "trends";

function qoeColor(score: number): string {
  if (score < 2.5) return "var(--risk-high)";
  if (score < 3.5) return "var(--risk-medium)";
  return "var(--risk-low)";
}

export default function ViewerExperience() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [anomalies, setAnomalies] = useState<Record<string, unknown>[]>([]);
  const [complaints, setComplaints] = useState<Record<string, unknown>[]>([]);
  const [selectedComplaint, setSelectedComplaint] = useState<Record<string, unknown> | null>(null);
  const [selectedSession, setSelectedSession] = useState<Record<string, unknown> | null>(null);
  const [catFilter, setCatFilter] = useState("");
  const [priFilter, setPriFilter] = useState("");

  const loadData = useCallback(async () => {
    try {
      const [c] = await Promise.all([
        apiGet<Record<string, unknown>[]>("/viewer/complaints?tenant_id=bein_sports&limit=50"),
      ]);
      setComplaints(c);
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredComplaints = complaints.filter((c) => {
    if (catFilter && c.category !== catFilter) return false;
    if (priFilter && c.priority !== priFilter) return false;
    return true;
  });

  const TABS: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "QoE Dashboard" },
    { key: "sessions", label: "Live Sessions" },
    { key: "anomalies", label: "Anomaly Feed" },
    { key: "complaints", label: "Complaints" },
    { key: "trends", label: "Trends" },
  ];

  const sentimentIcon = (s: unknown) => s === "positive" ? "😊" : s === "negative" ? "😠" : "😐";

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Viewer Experience</h2>

      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <MetricCard title="Avg QoE Score" value="—" unit="/5.0" trend="flat" />
            <MetricCard title="Sessions Today" value="0" trend="flat" />
            <MetricCard title="Anomalies Active" value="0" trend="flat" />
            <MetricCard title="Buffering Rate" value="—" unit="%" trend="flat" />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={[]} xKey="time" yKey="score" title="QoE Score Trend (24h)" color="var(--risk-low)" />
            </div>
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={[]} xKey="bucket" yKey="count" title="Startup Time Distribution" type="bar" color="var(--brand-primary)" />
            </div>
          </div>
        </div>
      )}

      {tab === "sessions" && (
        <div>
          <div className="flex gap-3 mb-4">
            <select className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="ended">Ended</option>
            </select>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable
              columns={[
                { key: "sessionId", label: "Session" },
                { key: "userIdHash", label: "User Hash" },
                { key: "bitrateAvg", label: "Bitrate" },
                { key: "bufferingRatio", label: "Buffer %" },
                { key: "qualityScore", label: "QoE", render: (v) => (
                  <span className="px-2 py-0.5 rounded text-xs font-bold" style={{ backgroundColor: `${qoeColor(v as number)}20`, color: qoeColor(v as number) }}>
                    {(v as number)?.toFixed(1) ?? "—"}
                  </span>
                )},
                { key: "status", label: "Status" },
              ]}
              data={[]}
              onRowClick={(row) => setSelectedSession(row)}
            />
          </div>
          {selectedSession && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => setSelectedSession(null)}>
              <div className="w-full max-w-lg rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
                <div className="flex justify-between mb-4">
                  <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Session Detail</h3>
                  <button onClick={() => setSelectedSession(null)} style={{ color: "var(--text-muted)" }}>✕</button>
                </div>
                <pre className="text-xs p-3 rounded overflow-auto max-h-64" style={{ backgroundColor: "var(--background)", color: "var(--text-secondary)" }}>
                  {JSON.stringify(selectedSession, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "anomalies" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{anomalies.length} anomalies</p>
            <button onClick={() => setAnomalies([])} className="text-xs px-3 py-1 rounded border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Clear</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            {anomalies.length === 0 ? (
              <div className="p-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Listening for QoE anomalies... No anomalies yet.</div>
            ) : (
              <LogTable columns={[
                { key: "timestamp", label: "Time" },
                { key: "sessionId", label: "Session" },
                { key: "anomalyType", label: "Type" },
                { key: "qoeScore", label: "QoE" },
                { key: "severity", label: "Severity", render: (v) => <SeverityBadge severity={v as SeverityLevel} /> },
              ]} data={anomalies.slice(0, 50)} />
            )}
          </div>
        </div>
      )}

      {tab === "complaints" && (
        <div>
          <div className="flex gap-3 mb-4 flex-wrap">
            <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Categories</option>
              {["buffering", "quality", "audio", "playback", "other"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={priFilter} onChange={(e) => setPriFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Priorities</option>
              {["P0", "P1", "P2", "P3"].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable
              columns={[
                { key: "id", label: "ID" },
                { key: "source", label: "Source" },
                { key: "category", label: "Category", render: (v) => <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>{String(v)}</span> },
                { key: "sentiment", label: "Sentiment", render: (v) => <span>{sentimentIcon(v)}</span> },
                { key: "priority", label: "Priority", render: (v) => <SeverityBadge severity={v as SeverityLevel} /> },
                { key: "status", label: "Status" },
                { key: "createdAt", label: "Created" },
              ]}
              data={filteredComplaints}
              onRowClick={(row) => setSelectedComplaint(row)}
            />
          </div>
          {selectedComplaint && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => setSelectedComplaint(null)}>
              <div className="w-full max-w-lg rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
                <div className="flex justify-between mb-4">
                  <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Complaint Detail</h3>
                  <button onClick={() => setSelectedComplaint(null)} style={{ color: "var(--text-muted)" }}>✕</button>
                </div>
                <pre className="text-xs p-3 rounded overflow-auto max-h-64" style={{ backgroundColor: "var(--background)", color: "var(--text-secondary)" }}>
                  {JSON.stringify(selectedComplaint, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "trends" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <RechartsWrapper data={[]} xKey="date" yKey="count" title="Complaint Volume by Category (30d)" color="var(--brand-accent)" />
          </div>
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <RechartsWrapper data={[]} xKey="date" yKey="events" title="QoE Degradation Events" color="var(--risk-high)" />
          </div>
        </div>
      )}

      <AgentChatPanel appName="Viewer Experience" />
    </div>
  );
}
