"use client";

import { useState } from "react";
import MetricCard from "@/components/ui/MetricCard";
import RiskBadge from "@/components/ui/RiskBadge";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiPost } from "@/lib/api";

type Tab = "retention" | "churn" | "analyst" | "insights";

function riskColor(score: number): string {
  if (score > 0.7) return "var(--risk-high)";
  if (score > 0.4) return "var(--risk-medium)";
  return "var(--risk-low)";
}

export default function GrowthRetention() {
  const [tab, setTab] = useState<Tab>("retention");
  const [riskFilter, setRiskFilter] = useState("");
  const [selectedSegment, setSelectedSegment] = useState<Record<string, unknown> | null>(null);
  const [nlQuery, setNlQuery] = useState("");
  const [queryResult, setQueryResult] = useState<{ sql: string; rows: Record<string, unknown>[]; interpretation: string } | null>(null);
  const [queryHistory, setQueryHistory] = useState<string[]>([]);
  const [queryLoading, setQueryLoading] = useState(false);

  const runQuery = async () => {
    if (!nlQuery.trim()) return;
    setQueryLoading(true);
    try {
      const result = await apiPost<{ generated_sql: string; rows: Record<string, unknown>[]; interpretation?: string }>("/growth/data-analyst/query", { tenant_id: "bein_sports", question: nlQuery });
      setQueryResult({ sql: result.generated_sql, rows: result.rows, interpretation: result.interpretation ?? "" });
      setQueryHistory((prev) => [nlQuery, ...prev.filter((q) => q !== nlQuery)].slice(0, 5));
    } catch { setQueryResult({ sql: "-- Error", rows: [], interpretation: "Query failed" }); }
    setQueryLoading(false);
  };

  const TABS: { key: Tab; label: string }[] = [
    { key: "retention", label: "Retention Dashboard" },
    { key: "churn", label: "Churn Risk" },
    { key: "analyst", label: "Data Analyst" },
    { key: "insights", label: "Insights" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Growth & Retention</h2>
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>{t.label}</button>
        ))}
      </div>

      {tab === "retention" && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <MetricCard title="Retention Rate 30d" value="—" unit="%" trend="flat" />
            <MetricCard title="Churn Rate" value="—" unit="%" trend="flat" />
            <MetricCard title="At-Risk Subscribers" value="0" trend="flat" />
            <MetricCard title="Avg LTV" value="—" unit="USD" trend="flat" />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={[]} xKey="month" yKey="rate" title="Monthly Retention Trend (12m)" color="var(--risk-low)" />
            </div>
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={[]} xKey="date" yKey="events" title="Churn Events Over Time" color="var(--risk-high)" />
            </div>
          </div>
        </div>
      )}

      {tab === "churn" && (
        <div>
          <div className="flex gap-3 mb-4">
            <select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Risk Levels</option>
              <option value="high">High (&gt;0.7)</option>
              <option value="medium">Medium (0.4-0.7)</option>
              <option value="low">Low (&lt;0.4)</option>
            </select>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "segmentName", label: "Segment" },
              { key: "subscriberCount", label: "Subscribers" },
              { key: "avgRiskScore", label: "Risk Score", render: (v) => {
                const val = v as number;
                return (
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-2 rounded-full" style={{ backgroundColor: "var(--border)" }}>
                      <div className="h-2 rounded-full" style={{ width: `${val * 100}%`, backgroundColor: riskColor(val) }} />
                    </div>
                    <span className="text-xs" style={{ color: riskColor(val) }}>{val?.toFixed(2)}</span>
                  </div>
                );
              }},
              { key: "trend", label: "Trend" },
              { key: "action", label: "Action", render: (_, row) => {
                const risk = (row.avgRiskScore as number) ?? 0;
                return risk > 0.7 ? (
                  <button onClick={(e) => { e.stopPropagation(); confirm("Send retention campaign? HIGH risk action."); }}
                    className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>Send Campaign</button>
                ) : null;
              }},
            ]} data={[]} onRowClick={(row) => setSelectedSegment(row)} />
          </div>
          {selectedSegment && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => setSelectedSegment(null)}>
              <div className="w-full max-w-lg rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
                <div className="flex justify-between mb-4">
                  <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Segment Detail</h3>
                  <button onClick={() => setSelectedSegment(null)} style={{ color: "var(--text-muted)" }}>✕</button>
                </div>
                <pre className="text-xs p-3 rounded overflow-auto max-h-64" style={{ backgroundColor: "var(--background)", color: "var(--text-secondary)" }}>
                  {JSON.stringify(selectedSegment, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "analyst" && (
        <div>
          <div className="mb-4">
            <textarea value={nlQuery} onChange={(e) => setNlQuery(e.target.value)} placeholder='e.g. "Show me top 10 tenants by error rate this week"'
              className="w-full text-sm px-4 py-3 rounded-lg border outline-none h-24 resize-none"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
            <div className="flex items-center gap-3 mt-2">
              <button onClick={runQuery} disabled={queryLoading} className="px-4 py-1.5 rounded text-sm font-medium disabled:opacity-50"
                style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>{queryLoading ? "Running..." : "Run Query"}</button>
              {queryHistory.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {queryHistory.map((q, i) => (
                    <button key={i} onClick={() => setNlQuery(q)} className="text-xs px-2 py-0.5 rounded border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>{q.slice(0, 30)}...</button>
                  ))}
                </div>
              )}
            </div>
          </div>
          {queryResult && (
            <div className="space-y-4">
              <details className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <summary className="text-xs cursor-pointer" style={{ color: "var(--text-muted)" }}>Generated SQL</summary>
                <pre className="text-xs mt-2 p-2 rounded font-mono overflow-x-auto" style={{ backgroundColor: "var(--background)", color: "var(--brand-primary)" }}>{queryResult.sql}</pre>
              </details>
              {queryResult.rows.length > 0 && (
                <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                  <LogTable columns={Object.keys(queryResult.rows[0]).map((k) => ({ key: k, label: k }))} data={queryResult.rows} />
                </div>
              )}
              {queryResult.interpretation && (
                <div className="rounded-lg border p-4 text-sm" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-secondary)" }}>
                  {queryResult.interpretation}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "insights" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>AI-generated growth insights</p>
            <button className="text-xs px-3 py-1 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>Refresh</button>
          </div>
          <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>No insights available. Run analysis to generate AI insights.</p>
          </div>
        </div>
      )}

      <AgentChatPanel appName="Growth & Retention" />
    </div>
  );
}
