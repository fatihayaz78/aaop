"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";

const APPS = [
  { name: "Ops Center", path: "/ops-center", icon: "📡" },
  { name: "Log Analyzer", path: "/log-analyzer", icon: "🔍" },
  { name: "Alert Center", path: "/alert-center", icon: "🔔" },
  { name: "Viewer Experience", path: "/viewer-experience", icon: "👁️" },
  { name: "Live Intelligence", path: "/live-intelligence", icon: "⚡" },
  { name: "Growth & Retention", path: "/growth-retention", icon: "📈" },
  { name: "Capacity & Cost", path: "/capacity-cost", icon: "⚙️" },
  { name: "Admin & Governance", path: "/admin-governance", icon: "🛡️" },
  { name: "AI Lab", path: "/ai-lab", icon: "🧪" },
  { name: "Knowledge Base", path: "/knowledge-base", icon: "📚" },
  { name: "DevOps Assistant", path: "/devops-assistant", icon: "🤖" },
];

interface DashData {
  total_incidents: number;
  open_incidents: number;
  mttr_p50_seconds: number;
  active_p0_count: number;
  severity_breakdown: Record<string, number>;
  incident_trend_24h: { hour: string; count: number }[];
  qoe: { avg_score: number; sessions_24h: number };
  events_24h: number;
  cdn_health: { error_rate_pct: number; cache_hit_rate_pct: number };
}

interface SLOItem { name: string; is_met: boolean }
interface AnomalyItem { detector: string; metric: string; severity: string; current_value: number; detected_at: string }

export default function DashboardPage() {
  const [dash, setDash] = useState<DashData | null>(null);
  const [slos, setSlos] = useState<SLOItem[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [decisions, setDecisions] = useState<Record<string, unknown>[]>([]);

  const load = useCallback(async () => {
    try { setDash(await apiGet<DashData>("/ops/dashboard")); } catch { /* ignore */ }
    try { setSlos(await apiGet<SLOItem[]>("/slo/status")); } catch { /* ignore */ }
    try { setAnomalies(await apiGet<AnomalyItem[]>("/realtime/anomalies?minutes=60")); } catch { /* ignore */ }
    try {
      const d = await apiGet<{ items: Record<string, unknown>[] }>("/ops/decisions");
      setDecisions(d.items?.slice(0, 5) || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const id = setInterval(load, 30000); return () => clearInterval(id); }, [load]);

  const sloMet = slos.filter((s) => s.is_met).length;
  const sloTotal = slos.length;
  const allMet = sloMet === sloTotal && sloTotal > 0;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
        Platform Dashboard
      </h2>

      {/* ── KPI Cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard label="Active Incidents" value={dash?.open_incidents ?? "—"} sub={`${dash?.active_p0_count ?? 0} P0`} color="var(--risk-high)" />
        <KPICard label="Events (24h)" value={dash?.events_24h ?? "—"} sub="detected" color="var(--risk-medium)" />
        <KPICard label="MTTR (P50)" value={dash ? `${Math.round(dash.mttr_p50_seconds / 60)}m` : "—"} sub="minutes" color="var(--brand-primary)" />
        <KPICard label="Avg QoE Score" value={dash?.qoe?.avg_score?.toFixed(1) ?? "—"} sub="/ 5.0" color="var(--risk-low)" />
      </div>

      {/* ── SLO + CDN + Severity row ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* SLO Status */}
        <div className="rounded-xl border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <h3 className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>SLO Status</h3>
          <div className="text-3xl font-bold" style={{ color: allMet ? "var(--risk-low)" : "var(--risk-high)" }}>
            {sloTotal > 0 ? `${sloMet}/${sloTotal}` : "—"}
          </div>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
            {allMet ? "All SLOs within budget" : `${sloTotal - sloMet} breached`}
          </p>
        </div>

        {/* CDN Health */}
        <div className="rounded-xl border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <h3 className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>CDN Health</h3>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold" style={{ color: (dash?.cdn_health?.error_rate_pct ?? 0) > 5 ? "var(--risk-high)" : "var(--risk-low)" }}>
              {dash?.cdn_health?.error_rate_pct?.toFixed(1) ?? "—"}%
            </span>
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>error rate</span>
          </div>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
            Cache hit: {dash?.cdn_health?.cache_hit_rate_pct?.toFixed(0) ?? "—"}%
          </p>
        </div>

        {/* Severity Breakdown */}
        <div className="rounded-xl border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <h3 className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>Severity Breakdown</h3>
          <div className="flex items-end gap-3 h-12">
            {["P0", "P1", "P2", "P3"].map((s) => {
              const val = dash?.severity_breakdown?.[s] ?? 0;
              const max = Math.max(...Object.values(dash?.severity_breakdown ?? { x: 1 }), 1);
              const colors: Record<string, string> = { P0: "#ef4444", P1: "#f59e0b", P2: "#3b82f6", P3: "#6b7280" };
              return (
                <div key={s} className="flex flex-col items-center gap-1 flex-1">
                  <div className="w-full rounded-t" style={{ height: `${Math.max((val / max) * 40, 4)}px`, backgroundColor: colors[s] }} />
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>{s}</span>
                  <span className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>{val}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Incident Trend 24h ── */}
      {dash?.incident_trend_24h && dash.incident_trend_24h.length > 0 && (
        <div className="rounded-xl border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <h3 className="text-xs font-semibold mb-3" style={{ color: "var(--text-muted)" }}>Incident Trend (24h)</h3>
          <div className="flex items-end gap-0.5 h-16">
            {dash.incident_trend_24h.map((h, i) => {
              const max = Math.max(...dash.incident_trend_24h.map((x) => x.count), 1);
              return (
                <div key={i} className="flex-1 rounded-t" title={`${h.hour}: ${h.count}`}
                  style={{ height: `${Math.max((h.count / max) * 60, 2)}px`, backgroundColor: h.count > 0 ? "var(--brand-primary)" : "var(--border)" }} />
              );
            })}
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>00:00</span>
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>23:00</span>
          </div>
        </div>
      )}

      {/* ── Live Anomaly Feed ── */}
      <div className="rounded-xl border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Live Anomaly Feed</h3>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>{anomalies.length} anomalies (1h)</span>
        </div>
        {anomalies.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>No anomalies detected</p>
        ) : (
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {anomalies.slice(0, 10).map((a, i) => {
              const sevColor: Record<string, string> = { P0: "var(--risk-high)", P1: "var(--risk-medium)", P2: "var(--risk-low)" };
              return (
                <div key={i} className="flex items-center gap-2 text-xs py-1 px-2 rounded" style={{ backgroundColor: "var(--background)" }}>
                  <span className="font-mono font-bold" style={{ color: sevColor[a.severity] || "var(--text-muted)" }}>{a.severity}</span>
                  <span style={{ color: "var(--text-secondary)" }}>{a.detector}</span>
                  <span style={{ color: "var(--text-muted)" }}>{a.metric}: {a.current_value}</span>
                  <span className="ml-auto" style={{ color: "var(--text-muted)" }}>{String(a.detected_at).slice(11, 19)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Applications Grid ── */}
      <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Applications</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {APPS.map((app) => (
          <Link key={app.path} href={app.path}
            className="rounded-xl p-4 border transition-colors hover:border-[var(--brand-primary)]"
            style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="flex items-center gap-2">
              <span className="text-lg">{app.icon}</span>
              <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{app.name}</span>
            </div>
          </Link>
        ))}
      </div>

      {/* ── Recent Decisions ── */}
      <div className="rounded-xl border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
        <h3 className="text-xs font-semibold mb-3" style={{ color: "var(--text-muted)" }}>Recent Agent Decisions</h3>
        {decisions.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>No recent decisions</p>
        ) : (
          <div className="space-y-1">
            {decisions.map((d, i) => (
              <div key={i} className="flex items-center gap-2 text-xs py-1 px-2 rounded" style={{ backgroundColor: "var(--background)" }}>
                <span className="font-medium" style={{ color: "var(--text-primary)" }}>{String(d.app || "—")}</span>
                <span style={{ color: "var(--text-secondary)" }}>{String(d.action || "—")}</span>
                <span className="ml-auto font-mono" style={{ color: "var(--text-muted)" }}>{String(d.created_at || "").slice(0, 16)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <AgentChatPanel appName="Platform" />
    </div>
  );
}

function KPICard({ label, value, sub, color }: { label: string; value: string | number; sub: string; color: string }) {
  return (
    <div className="rounded-xl border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
      <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-bold" style={{ color }}>{value}</span>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>{sub}</span>
      </div>
    </div>
  );
}
