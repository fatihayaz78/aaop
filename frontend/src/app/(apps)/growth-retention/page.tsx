"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost } from "@/lib/api";
import type { GrowthDashboard, RetentionScore } from "@/types/growth_retention";

type Tab = "dashboard" | "retention" | "churn" | "segments" | "query";

const segColor: Record<string, string> = { power_user: "var(--risk-low)", regular: "var(--brand-primary)", at_risk: "var(--risk-medium)", churned: "var(--risk-high)" };
const segBg: Record<string, string> = { power_user: "var(--risk-low-bg)", regular: "var(--brand-glow)", at_risk: "var(--risk-medium-bg)", churned: "var(--risk-high-bg)" };
const churnColor = (v: number) => v > 0.7 ? "var(--risk-high)" : v > 0.3 ? "var(--risk-medium)" : "var(--risk-low)";
const qoeColor = (v: number) => v >= 4 ? "var(--risk-low)" : v >= 3 ? "var(--risk-medium)" : "var(--risk-high)";

export default function GrowthRetention() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [dash, setDash] = useState<GrowthDashboard | null>(null);
  const [retention, setRetention] = useState<RetentionScore[]>([]);
  const [churnUsers, setChurnUsers] = useState<RetentionScore[]>([]);
  const [segments, setSegments] = useState<Record<string, unknown>[]>([]);
  const [segFilter, setSegFilter] = useState("");
  const [queryInput, setQueryInput] = useState("");
  const [queryResult, setQueryResult] = useState<Record<string, unknown> | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);

  const loadDash = useCallback(async () => {
    try { setDash(await apiGet<GrowthDashboard>("/growth/dashboard")); } catch { /* */ }
  }, []);

  useEffect(() => { loadDash(); }, [loadDash]);
  useEffect(() => {
    if (tab === "dashboard") { const i = setInterval(loadDash, 60000); return () => clearInterval(i); }
    if (tab === "retention") { (async () => { try { const r = await apiGet<{ items: RetentionScore[] }>(`/growth/retention?limit=50${segFilter ? `&segment=${segFilter}` : ""}`); setRetention(r.items ?? []); } catch { /* */ } })(); }
    if (tab === "churn") { (async () => { try { const r = await apiGet<{ items: RetentionScore[] }>("/growth/churn-risk"); setChurnUsers(r.items ?? []); } catch { /* */ } })(); }
    if (tab === "segments") { (async () => { try { const r = await apiGet<{ segments: Record<string, unknown>[] }>("/growth/segments"); setSegments(r.segments ?? []); } catch { /* */ } })(); }
  }, [tab, segFilter, loadDash]);

  const submitQuery = async (q: string) => {
    if (!q.trim()) return;
    setQueryLoading(true); setQueryResult(null);
    try { setQueryResult(await apiPost("/growth/query", { question: q })); } catch { setQueryResult({ error: "Query failed" }); }
    setQueryLoading(false);
  };

  const segPieData = dash ? Object.entries(dash.segment_breakdown).map(([k, v]) => ({ segment: k, count: v })) : [];

  const TABS: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "Dashboard" }, { key: "retention", label: "Retention" },
    { key: "churn", label: "Churn Risk" }, { key: "segments", label: "Segments" },
    { key: "query", label: "AI Query" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Growth & Retention</h2>
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Empty data state */}
      {!dash && tab === "dashboard" && (
        <div className="flex flex-col items-center justify-center py-20">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
          <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>No data available</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>Connect a data source and run sync to populate this view.</p>
          <a href="/admin-governance" className="mt-3 text-xs px-3 py-1.5 rounded-lg" style={{ background: "var(--brand-primary)", color: "#fff" }}>Go to Data Sources →</a>
        </div>
      )}

      {tab === "dashboard" && dash && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Total Users" value={dash.total_users} />
            <MetricCard title="At-Risk Users" value={dash.at_risk_users} />
            <MetricCard title="Avg Churn Risk" value={`${(dash.avg_churn_risk * 100).toFixed(1)}%`} />
            <MetricCard title="Avg QoE Score" value={dash.avg_qoe_score.toFixed(2)} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={segPieData} xKey="segment" yKey="count" title="Segment Breakdown" height={200} type="bar" />
            </div>
            <div className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={dash.churn_trend_7d} xKey="date" yKey="at_risk_count" title="Churn Trend (7d)" height={200} type="line" />
            </div>
            <div className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={dash.top_churn_reasons} xKey="reason" yKey="count" title="Top Churn Reasons" height={200} type="bar" />
            </div>
          </div>
        </div>
      )}

      {tab === "retention" && (
        <div>
          <div className="flex gap-3 mb-4">
            <select value={segFilter} onChange={(e) => setSegFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Segments</option>
              {["power_user", "regular", "at_risk", "churned"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "user_id_hash", label: "User", render: (v) => <span className="font-mono text-xs">{String(v).slice(0, 12)}...</span> },
              { key: "churn_risk", label: "Churn Risk", render: (v) => {
                const val = Number(v);
                return (<div className="flex items-center gap-2"><div className="w-16 h-1.5 rounded-full" style={{ backgroundColor: "var(--border)" }}><div className="h-1.5 rounded-full" style={{ width: `${val * 100}%`, backgroundColor: churnColor(val) }} /></div><span className="text-xs" style={{ color: churnColor(val) }}>{(val * 100).toFixed(0)}%</span></div>);
              }},
              { key: "qoe_score", label: "QoE", render: (v) => <span style={{ color: qoeColor(Number(v)) }}>{Number(v).toFixed(2)}</span> },
              { key: "segment", label: "Segment", render: (v) => <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: segBg[String(v)], color: segColor[String(v)] }}>{String(v)}</span> },
              { key: "last_active", label: "Last Active", render: (v) => <span className="text-xs">{String(v).slice(0, 10)}</span> },
            ]} data={retention as unknown as Record<string, unknown>[]} />
          </div>
        </div>
      )}

      {tab === "churn" && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>High Risk Users</h3>
            <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>{churnUsers.length}</span>
          </div>
          {churnUsers.length === 0 ? (
            <div className="rounded-lg border p-12 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>No high-risk users detected</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {churnUsers.map((u) => (
                <div key={u.id} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--risk-high)" }}>
                  <p className="text-xs font-mono mb-1" style={{ color: "var(--text-muted)" }}>{u.user_id_hash?.slice(0, 16)}</p>
                  <p className="text-2xl font-bold" style={{ color: "var(--risk-high)" }}>{(u.churn_risk * 100).toFixed(0)}%</p>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>QoE: {u.qoe_score?.toFixed(2)} | Last: {u.last_active?.slice(0, 10)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "segments" && (
        <div className="space-y-4">
          {segments.map((s) => (
            <div key={String(s.name)} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-sm font-semibold" style={{ color: segColor[String(s.name)] }}>{String(s.name)}</span>
                <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--background)", color: "var(--text-secondary)" }}>{Number(s.count)} users</span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>Churn: {((Number(s.avg_churn_risk) || 0) * 100).toFixed(0)}% | QoE: {Number(s.avg_qoe || 0).toFixed(2)}</span>
              </div>
              <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>{String(s.description || "")}</p>
              <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>{String(s.recommended_action || "")}</span>
            </div>
          ))}
        </div>
      )}

      {tab === "query" && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <input type="text" value={queryInput} onChange={(e) => setQueryInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitQuery(queryInput)} placeholder="Ask anything about your data..."
              className="flex-1 text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
            <button onClick={() => submitQuery(queryInput)} disabled={queryLoading} className="px-4 py-2 rounded text-sm font-medium disabled:opacity-50" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
              {queryLoading ? "Analyzing..." : "Ask"}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {["Show top 10 at-risk users", "Average QoE by segment", "Churn risk trend this week", "Compare power users vs at-risk"].map((q) => (
              <button key={q} onClick={() => { setQueryInput(q); submitQuery(q); }} className="text-xs px-2 py-1 rounded border" style={{ borderColor: "var(--brand-primary)", color: "var(--brand-primary)" }}>{q}</button>
            ))}
          </div>
          {queryResult && (() => {
            const qr = queryResult as { error?: string; sql?: string; results?: Record<string, unknown>[]; row_count?: number };
            return (
            <div className="space-y-3">
              {qr.error && <div className="rounded p-3 text-sm" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>{qr.error}</div>}
              {qr.sql && (
                <details><summary className="text-xs cursor-pointer" style={{ color: "var(--text-muted)" }}>SQL Query</summary>
                  <pre className="mt-1 text-xs p-2 rounded font-mono overflow-x-auto" style={{ backgroundColor: "var(--background)", color: "var(--text-secondary)" }}>{qr.sql}</pre>
                </details>
              )}
              {Array.isArray(qr.results) && qr.results.length > 0 && (
                <div className="rounded-lg border overflow-x-auto" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                  <table className="w-full text-sm"><thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {Object.keys(qr.results[0]).map((k) => <th key={k} className="text-left px-3 py-2 text-xs font-medium" style={{ color: "var(--text-muted)" }}>{k}</th>)}
                  </tr></thead><tbody>
                    {qr.results.slice(0, 20).map((row, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>{Object.values(row).map((v, j) => <td key={j} className="px-3 py-1 text-xs" style={{ color: "var(--text-secondary)" }}>{String(v ?? "")}</td>)}</tr>
                    ))}
                  </tbody></table>
                  <p className="text-xs p-2" style={{ color: "var(--text-muted)" }}>{qr.row_count ?? 0} rows</p>
                </div>
              )}
            </div>
          ); })()}
        </div>
      )}

      <AgentChatPanel appName="Growth & Retention" />
    </div>
  );
}
