"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost } from "@/lib/api";
import type { ViewerDashboard, QoEMetric, Complaint } from "@/types/viewer_experience";

type Tab = "dashboard" | "sessions" | "anomalies" | "complaints" | "trends" | "segments";

const scoreColor = (s: number) => s >= 4 ? "var(--risk-low)" : s >= 3 ? "var(--risk-medium)" : "var(--risk-high)";
const sentimentEmoji: Record<string, string> = { negative: "\uD83D\uDE1E", neutral: "\uD83D\uDE10", positive: "\uD83D\uDE0A", pending: "\u2753" };

export default function ViewerExperience() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [dash, setDash] = useState<ViewerDashboard | null>(null);
  const [sessions, setSessions] = useState<QoEMetric[]>([]);
  const [anomalies, setAnomalies] = useState<QoEMetric[]>([]);
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [trends, setTrends] = useState<Record<string, unknown>>({});
  const [deviceFilter, setDeviceFilter] = useState("");
  const [contentFilter, setContentFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [showComplaintForm, setShowComplaintForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newCat, setNewCat] = useState("buffering");
  const [newContent, setNewContent] = useState("");

  const loadDashboard = useCallback(async () => {
    try { setDash(await apiGet<ViewerDashboard>("/viewer/dashboard")); } catch { /* */ }
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      let url = "/viewer/qoe/metrics?limit=50";
      if (deviceFilter) url += `&device=${deviceFilter}`;
      if (contentFilter) url += `&content_type=${contentFilter}`;
      const res = await apiGet<{ items: QoEMetric[] }>(url);
      setSessions(res.items ?? []);
    } catch { /* */ }
  }, [deviceFilter, contentFilter]);

  const loadAnomalies = useCallback(async () => {
    try { const res = await apiGet<{ items: QoEMetric[] }>("/viewer/qoe/anomalies"); setAnomalies(res.items ?? []); } catch { /* */ }
  }, []);

  const loadComplaints = useCallback(async () => {
    try {
      let url = "/viewer/complaints?limit=50";
      if (statusFilter) url += `&status=${statusFilter}`;
      if (priorityFilter) url += `&priority=${priorityFilter}`;
      if (catFilter) url += `&category=${catFilter}`;
      const res = await apiGet<{ items: Complaint[] }>(url);
      setComplaints(res.items ?? []);
    } catch { /* */ }
  }, [statusFilter, priorityFilter, catFilter]);

  const loadTrends = useCallback(async () => {
    try { setTrends(await apiGet("/viewer/trends")); } catch { /* */ }
  }, []);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);
  useEffect(() => {
    if (tab === "sessions") loadSessions();
    if (tab === "anomalies") loadAnomalies();
    if (tab === "complaints") loadComplaints();
    if (tab === "trends") loadTrends();
  }, [tab, loadSessions, loadAnomalies, loadComplaints, loadTrends]);

  // Poll dashboard 30s
  useEffect(() => {
    if (tab !== "dashboard") return;
    const i = setInterval(loadDashboard, 30000);
    return () => clearInterval(i);
  }, [tab, loadDashboard]);

  // Poll anomalies 60s
  useEffect(() => {
    if (tab !== "anomalies") return;
    const i = setInterval(loadAnomalies, 60000);
    return () => clearInterval(i);
  }, [tab, loadAnomalies]);

  const submitComplaint = async () => {
    if (!newTitle) return;
    await apiPost("/viewer/complaints", { title: newTitle, category: newCat, content: newContent });
    setNewTitle(""); setNewContent(""); setShowComplaintForm(false);
    loadComplaints();
  };

  const TABS: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "QoE Dashboard" }, { key: "sessions", label: "Live Sessions" },
    { key: "anomalies", label: "Anomaly Feed" }, { key: "complaints", label: "Complaints" },
    { key: "trends", label: "Trends" }, { key: "segments", label: "Segments" },
  ];

  const distData = dash ? [
    { label: "Excellent", count: dash.score_distribution.excellent, fill: "#22c55e" },
    { label: "Good", count: dash.score_distribution.good, fill: "#3b82f6" },
    { label: "Fair", count: dash.score_distribution.fair, fill: "#eab308" },
    { label: "Poor", count: dash.score_distribution.poor, fill: "#ef4444" },
  ] : [];

  const devData = dash ? Object.entries(dash.device_breakdown).map(([k, v]) => ({ device: k, count: v })) : [];

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

      {/* ═══ QoE Dashboard ═══ */}
      {tab === "dashboard" && dash && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Avg QoE Score" value={dash.avg_qoe_score.toFixed(2)} />
            <MetricCard title="Below Threshold" value={dash.sessions_below_threshold} />
            <MetricCard title="Active Complaints" value={dash.active_complaints} />
            <MetricCard title="Sessions 24h" value={dash.total_sessions_24h} />
          </div>
          {/* QoE Gauge */}
          <div className="flex justify-center">
            <div className="relative w-40 h-40">
              <svg viewBox="0 0 100 100" className="w-full h-full">
                <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border)" strokeWidth="8" />
                <circle cx="50" cy="50" r="42" fill="none" stroke={scoreColor(dash.avg_qoe_score)}
                  strokeWidth="8" strokeDasharray={`${(dash.avg_qoe_score / 5) * 264} 264`}
                  strokeLinecap="round" transform="rotate(-90 50 50)" />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-bold" style={{ color: scoreColor(dash.avg_qoe_score) }}>{dash.avg_qoe_score.toFixed(1)}</span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>/ 5.0</span>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={distData} xKey="label" yKey="count" title="Score Distribution" height={180} type="bar" />
            </div>
            <div className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={devData} xKey="device" yKey="count" title="Device Breakdown" height={180} type="bar" />
            </div>
            <div className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={dash.qoe_trend_24h} xKey="hour" yKey="avg_score" title="QoE Trend 24h" height={180} type="line" />
            </div>
          </div>
        </div>
      )}

      {/* ═══ Live Sessions ═══ */}
      {tab === "sessions" && (
        <div>
          <div className="flex gap-3 mb-4">
            <select value={deviceFilter} onChange={(e) => { setDeviceFilter(e.target.value); }}
              className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Devices</option>
              {["mobile", "desktop", "smarttv", "tablet"].map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <select value={contentFilter} onChange={(e) => { setContentFilter(e.target.value); }}
              className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Content</option>
              <option value="live">Live</option><option value="vod">VOD</option>
            </select>
            <button onClick={loadSessions} className="px-3 py-1.5 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Refresh</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "session_id", label: "Session", render: (v) => <span className="font-mono text-xs">{String(v).slice(0, 12)}...</span> },
              { key: "quality_score", label: "QoE", render: (v) => <span style={{ color: scoreColor(Number(v)) }}>{Number(v).toFixed(2)}</span> },
              { key: "device_type", label: "Device" }, { key: "region", label: "Region" },
              { key: "buffering_ratio", label: "Buffer %", render: (v) => <span>{(Number(v) * 100).toFixed(1)}%</span> },
              { key: "startup_time_ms", label: "Startup", render: (v) => <span>{Number(v)}ms</span> },
            ]} data={sessions as unknown as Record<string, unknown>[]} />
          </div>
        </div>
      )}

      {/* ═══ Anomaly Feed ═══ */}
      {tab === "anomalies" && (
        <div>
          {anomalies.length === 0 ? (
            <div className="rounded-lg border p-12 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <div className="text-3xl mb-2" style={{ color: "var(--risk-low)" }}>&#10003;</div>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>No QoE anomalies in the last 24h</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {anomalies.map((a, i) => (
                <div key={i} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--risk-high)" }}>
                  <div className="text-2xl font-bold mb-2" style={{ color: "var(--risk-high)" }}>{Number((a as any).quality_score ?? a.qoe_score).toFixed(2)}</div>
                  <p className="text-xs font-mono mb-1" style={{ color: "var(--text-muted)" }}>{a.session_id?.slice(0, 16)}</p>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{a.device_type} | {a.region}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ Complaints ═══ */}
      {tab === "complaints" && (
        <div>
          <div className="flex gap-3 mb-4 flex-wrap">
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Status</option><option value="open">Open</option><option value="resolved">Resolved</option>
            </select>
            <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Priority</option><option value="P1">P1</option><option value="P2">P2</option><option value="P3">P3</option>
            </select>
            <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Categories</option>
              {["buffering", "playback_error", "audio_sync", "login_issue", "content_quality", "subtitle"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <button onClick={() => setShowComplaintForm(!showComplaintForm)} className="px-3 py-1.5 rounded text-sm font-medium"
              style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Submit Complaint</button>
          </div>
          {showComplaintForm && (
            <div className="rounded-lg border p-4 mb-4 space-y-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <input type="text" placeholder="Title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)}
                className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              <select value={newCat} onChange={(e) => setNewCat(e.target.value)}
                className="text-sm px-3 py-2 rounded border" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                {["buffering", "playback_error", "audio_sync", "login_issue", "content_quality", "subtitle"].map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <textarea placeholder="Details..." value={newContent} onChange={(e) => setNewContent(e.target.value)} rows={3}
                className="w-full text-sm px-3 py-2 rounded border outline-none resize-y" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              <button onClick={submitComplaint} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Submit</button>
            </div>
          )}
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "priority", label: "Priority", render: (v) => <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: v === "P1" ? "var(--risk-high-bg)" : v === "P2" ? "var(--risk-medium-bg)" : "var(--risk-low-bg)", color: v === "P1" ? "var(--risk-high)" : v === "P2" ? "var(--risk-medium)" : "var(--risk-low)" }}>{String(v)}</span> },
              { key: "title", label: "Title" },
              { key: "category", label: "Category" },
              { key: "sentiment", label: "Mood", render: (v) => <span>{sentimentEmoji[String(v)] || "?"}</span> },
              { key: "status", label: "Status" },
              { key: "created_at", label: "Time", render: (v) => <span className="text-xs">{String(v).slice(0, 16)}</span> },
            ]} data={complaints as unknown as Record<string, unknown>[]} />
          </div>
        </div>
      )}

      {/* ═══ Trends ═══ */}
      {tab === "trends" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <RechartsWrapper data={(trends as any).qoe_by_device ?? []} xKey="device" yKey="avg_score" title="QoE by Device" height={200} type="bar" />
          </div>
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <RechartsWrapper data={(trends as any).qoe_by_region ?? []} xKey="region" yKey="avg_score" title="QoE by Region" height={200} type="bar" />
          </div>
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <RechartsWrapper data={(trends as any).complaint_categories ?? []} xKey="category" yKey="count" title="Complaint Categories" height={200} type="bar" />
          </div>
        </div>
      )}

      {/* ═══ Segments ═══ */}
      {tab === "segments" && (
        <div>
          <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>Segment analysis coming soon — requires 30 days of data</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[{ name: "Power Users", desc: "High engagement, QoE >4.0", count: "~12K", color: "var(--risk-low)" },
              { name: "At-Risk", desc: "QoE declining, buffering >5%", count: "~3.2K", color: "var(--risk-high)" },
              { name: "New Viewers", desc: "First session <7 days ago", count: "~8.5K", color: "var(--brand-primary)" }].map((s) => (
              <div key={s.name} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <h4 className="text-sm font-semibold" style={{ color: s.color }}>{s.name}</h4>
                <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>{s.desc}</p>
                <p className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{s.count}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <AgentChatPanel appName="Viewer Experience" />
    </div>
  );
}
