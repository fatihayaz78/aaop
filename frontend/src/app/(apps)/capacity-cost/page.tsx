"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet } from "@/lib/api";
import type { CapacityDashboard } from "@/types/capacity_cost";

type Tab = "dashboard" | "forecast" | "usage" | "jobs" | "cost";

const utilColor = (v: number) => v > 90 ? "var(--risk-high)" : v > 70 ? "var(--risk-medium)" : "var(--risk-low)";
const utilBg = (v: number) => v > 90 ? "var(--risk-high-bg)" : v > 70 ? "var(--risk-medium-bg)" : "var(--risk-low-bg)";
const fmtUsd = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

export default function CapacityCost() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [dash, setDash] = useState<CapacityDashboard | null>(null);
  const [forecast, setForecast] = useState<Record<string, unknown>[]>([]);
  const [usage, setUsage] = useState<Record<string, unknown>[]>([]);
  const [jobs, setJobs] = useState<Record<string, unknown>[]>([]);
  const [cost, setCost] = useState<Record<string, unknown> | null>(null);
  const [svcFilter, setSvcFilter] = useState("");

  const loadDash = useCallback(async () => {
    try { setDash(await apiGet<CapacityDashboard>("/capacity/dashboard")); } catch { /* */ }
  }, []);

  useEffect(() => { loadDash(); }, [loadDash]);
  useEffect(() => {
    if (tab === "dashboard") { const i = setInterval(loadDash, 30000); return () => clearInterval(i); }
    if (tab === "forecast") { (async () => { try { const r = await apiGet<{ forecast: Record<string, unknown>[] }>("/capacity/forecast"); setForecast(r.forecast ?? []); } catch { /* */ } })(); }
    if (tab === "usage") { (async () => { try { const r = await apiGet<{ items: Record<string, unknown>[] }>(`/capacity/usage?limit=100${svcFilter ? `&service=${svcFilter}` : ""}`); setUsage(r.items ?? []); } catch { /* */ } })(); }
    if (tab === "jobs") { (async () => { try { setJobs(await apiGet("/capacity/jobs")); } catch { /* */ } })(); }
    if (tab === "cost") { (async () => { try { setCost(await apiGet("/capacity/cost")); } catch { /* */ } })(); }
  }, [tab, svcFilter, loadDash]);

  const TABS: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "Dashboard" }, { key: "forecast", label: "Forecast" },
    { key: "usage", label: "Usage" }, { key: "jobs", label: "Automation Jobs" },
    { key: "cost", label: "Cost" },
  ];

  const filteredForecast = svcFilter ? forecast.filter((f) => f.service === svcFilter) : forecast;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Capacity & Cost</h2>
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
            <MetricCard title="Warning Services" value={dash.services_at_warning} />
            <MetricCard title="Critical Services" value={dash.services_at_critical} />
            <MetricCard title="Avg Utilization" value={`${dash.avg_utilization}%`} />
            <MetricCard title="Monthly Cost Est." value={fmtUsd(dash.cost_estimate_monthly)} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <h3 className="text-xs font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Utilization by Service</h3>
              <div className="space-y-2">
                {dash.utilization_by_service.map((s) => (
                  <div key={s.service} className="flex items-center gap-3">
                    <span className="text-xs w-32 truncate" style={{ color: "var(--text-secondary)" }}>{s.service}</span>
                    <div className="flex-1 h-2 rounded-full" style={{ backgroundColor: "var(--border)" }}>
                      <div className="h-2 rounded-full transition-all" style={{ width: `${Math.min(s.pct, 100)}%`, backgroundColor: utilColor(s.pct) }} />
                    </div>
                    <span className="text-xs w-12 text-right" style={{ color: utilColor(s.pct) }}>{s.pct.toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={dash.utilization_trend_24h} xKey="hour" yKey="avg_pct" title="Utilization Trend (24h)" height={200} type="line" />
            </div>
          </div>
        </div>
      )}

      {tab === "forecast" && (
        <div>
          <div className="flex gap-3 mb-4">
            <select value={svcFilter} onChange={(e) => setSvcFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Services</option>
              {["cdn_bandwidth", "concurrent_streams", "origin_cpu"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "date", label: "Date" },
              { key: "service", label: "Service" },
              { key: "predicted_pct", label: "Predicted %", render: (v) => <span style={{ color: utilColor(Number(v)) }}>{Number(v).toFixed(1)}%</span> },
              { key: "confidence", label: "Confidence", render: (v) => <span>{(Number(v) * 100).toFixed(0)}%</span> },
              { key: "recommendation", label: "Recommendation", render: (v) => {
                const r = String(v);
                const c = r === "scale_up" ? "var(--risk-high)" : r === "monitor" ? "var(--risk-medium)" : "var(--risk-low)";
                const bg = r === "scale_up" ? "var(--risk-high-bg)" : r === "monitor" ? "var(--risk-medium-bg)" : "var(--risk-low-bg)";
                return <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: bg, color: c }}>{r}</span>;
              }},
            ]} data={filteredForecast as unknown as Record<string, unknown>[]} />
          </div>
        </div>
      )}

      {tab === "usage" && (
        <div>
          <div className="flex gap-3 mb-4">
            <select value={svcFilter} onChange={(e) => setSvcFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Services</option>
              {["cdn_bandwidth", "origin_cpu", "origin_memory", "encoder_queue", "api_gateway", "cache_hit_rate", "concurrent_streams"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "timestamp", label: "Time", render: (v) => <span className="text-xs">{String(v).slice(11, 16)}</span> },
              { key: "service", label: "Service" },
              { key: "metric_name", label: "Metric" },
              { key: "current_value", label: "Value", render: (v) => <span>{Number(v).toFixed(1)}</span> },
              { key: "capacity_limit", label: "Limit" },
              { key: "utilization_pct", label: "Util %", render: (v) => <span style={{ color: utilColor(Number(v)) }}>{Number(v).toFixed(1)}%</span> },
            ]} data={usage as unknown as Record<string, unknown>[]} />
          </div>
        </div>
      )}

      {tab === "jobs" && (
        <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <LogTable columns={[
            { key: "name", label: "Name" },
            { key: "job_type", label: "Type" },
            { key: "status", label: "Status", render: (v) => {
              const s = String(v);
              const c = s === "active" ? "var(--risk-low)" : s === "paused" ? "var(--risk-medium)" : "var(--text-muted)";
              const bg = s === "active" ? "var(--risk-low-bg)" : s === "paused" ? "var(--risk-medium-bg)" : "var(--background)";
              return <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: bg, color: c }}>{s}</span>;
            }},
            { key: "schedule", label: "Schedule", render: (v) => <span className="text-xs font-mono">{String(v)}</span> },
            { key: "last_run", label: "Last Run", render: (v) => <span className="text-xs">{String(v ?? "—").slice(0, 16)}</span> },
          ]} data={jobs as unknown as Record<string, unknown>[]} />
        </div>
      )}

      {tab === "cost" && cost && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg border p-4 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Current Month</p>
              <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{fmtUsd(Number(cost.current_month_usd))}</p>
            </div>
            <div className="rounded-lg border p-4 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Projected</p>
              <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{fmtUsd(Number(cost.projected_month_usd))}</p>
            </div>
            <div className="rounded-lg border p-4 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>vs Last Month</p>
              <p className="text-2xl font-bold" style={{ color: Number(cost.vs_last_month_pct) > 0 ? "var(--risk-high)" : "var(--risk-low)" }}>
                {Number(cost.vs_last_month_pct) > 0 ? "+" : ""}{Number(cost.vs_last_month_pct).toFixed(1)}%
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={(cost.breakdown as Record<string, unknown>[]) ?? []} xKey="service" yKey="cost_usd" title="Cost Breakdown" height={200} type="bar" />
            </div>
            <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <LogTable columns={[
                { key: "service", label: "Service" },
                { key: "cost_usd", label: "Cost", render: (v) => <span>{fmtUsd(Number(v))}</span> },
                { key: "pct_of_total", label: "% of Total", render: (v) => <span>{Number(v).toFixed(1)}%</span> },
              ]} data={(cost.breakdown as Record<string, unknown>[]) ?? []} />
            </div>
          </div>
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <h3 className="text-xs font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Optimization Tips</h3>
            <div className="space-y-2">
              {((cost.optimization_tips as string[]) ?? []).map((tip, i) => (
                <div key={i} className="flex items-start gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                  <span style={{ color: "var(--risk-medium)" }}>&#128161;</span>
                  <span>{tip}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <AgentChatPanel appName="Capacity & Cost" />
    </div>
  );
}
