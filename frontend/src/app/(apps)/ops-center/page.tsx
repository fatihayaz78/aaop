"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import RiskBadge from "@/components/ui/RiskBadge";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost, apiPatch, exportToCsv } from "@/lib/api";
import { useOpsWebSocket } from "@/lib/socket";
import type { Incident, OpsMetrics, AgentDecision, RCAResult, RiskLevel } from "@/types";

type Tab = "dashboard" | "incidents" | "rca" | "decisions" | "about";
type TimeRange = "1h" | "6h" | "24h" | "7d";

/* ── FIX 7: MTTR format helper ── */
const formatMTTR = (seconds: number | null | undefined): string => {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
};

/* ── Severity badge with correct colors (FIX 4) ── */
const SEV_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  P0: { bg: "#450a0a", text: "#fca5a5", border: "#991b1b" },
  P1: { bg: "#431407", text: "#fdba74", border: "#9a3412" },
  P2: { bg: "#422006", text: "#fde047", border: "#854d0e" },
  P3: { bg: "#172554", text: "#93c5fd", border: "#1e40af" },
};

const SevBadge = ({ severity }: { severity: string }) => {
  const c = SEV_COLORS[severity] || SEV_COLORS.P3;
  return (
    <span className="text-xs px-2 py-0.5 rounded border font-medium"
      style={{ backgroundColor: c.bg, color: c.text, borderColor: c.border }}>
      {severity}
    </span>
  );
};

/* ── FIX 5: Status dot ── */
const StatusDot = ({ status }: { status: string }) => {
  const color = status === "open" ? "#f87171" : status === "investigating" ? "#fbbf24" : "#4ade80";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: color }} />
      {status}
    </span>
  );
};

/* ── Severity bar chart colors (FIX 2) ── */
const SEV_BAR_COLORS: Record<string, string> = { P0: "#ef4444", P1: "#f97316", P2: "#eab308", P3: "#3b82f6" };

export default function OpsCenter() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [dashboardRaw, setDashboardRaw] = useState<Record<string, unknown>>({});
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [severityFilter, setSeverityFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [timeRange, setTimeRange] = useState<TimeRange>("24h");
  const [rcaPolling, setRcaPolling] = useState<string | null>(null);
  const [rcaResult, setRcaResult] = useState<RCAResult | null>(null);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [showAddIncident, setShowAddIncident] = useState(false);
  const [addForm, setAddForm] = useState({ title: "", severity: "P2", description: "", affected_service: "" });
  const [addError, setAddError] = useState("");
  const [addLoading, setAddLoading] = useState(false);
  const [rcaIncidentId, setRcaIncidentId] = useState("");
  const [rcaLoading, setRcaLoading] = useState(false);
  const [rcaData, setRcaData] = useState<Record<string, unknown> | null>(null);
  const { incidents: wsIncidents } = useOpsWebSocket();

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const mapMetrics = (raw: any): OpsMetrics => ({
    openIncidents: raw.open_incidents ?? raw.openIncidents ?? 0,
    mttrP50: raw.mttr_p50_seconds ?? raw.mttrP50 ?? 0,
    activeTenants: raw.active_p0_count ?? raw.activeTenants ?? 0,
    decisionsLast24h: raw.total_incidents ?? raw.decisionsLast24h ?? 0,
    p0Open: raw.active_p0_count ?? raw.p0Open ?? 0,
    p1Open: 0,
    rcaComplete: 0,
  });

  const mapIncident = (i: any): Incident => ({
    ...i,
    incidentId: i.incident_id ?? i.incidentId ?? "",
    tenantId: i.tenant_id ?? i.tenantId ?? "",
    severity: i.severity ?? "P3",
    title: i.title ?? "",
    status: i.status ?? "open",
    sourceApp: i.source_app ?? i.sourceApp ?? "",
    affectedServices: i.affected_svcs ?? i.affected_services ?? i.affectedServices ?? [],
    mttrSeconds: i.mttr_seconds ?? i.mttrSeconds,
    summaryTr: i.summary_tr ?? i.summaryTr ?? "",
    detailEn: i.detail_en ?? i.detailEn ?? "",
    createdAt: i.created_at ?? i.createdAt ?? "",
    updatedAt: i.updated_at ?? i.updatedAt ?? "",
  });
  /* eslint-enable @typescript-eslint/no-explicit-any */

  const loadData = useCallback(async () => {
    try {
      const [rawMetrics, rawInc, dec] = await Promise.all([
        apiGet<Record<string, unknown>>("/ops/dashboard?tenant_id=ott_co"),
        apiGet<Record<string, unknown>>("/ops/incidents?tenant_id=ott_co&limit=50"),
        apiGet<Record<string, unknown>>("/ops/decisions?tenant_id=ott_co&limit=100").catch(() => ({ items: [] })),
      ]);
      setDashboardRaw(rawMetrics);
      setMetrics(mapMetrics(rawMetrics));
      const incItems = (rawInc as any).items ?? rawInc;
      setIncidents(Array.isArray(incItems) ? incItems.map(mapIncident) : []);
      const decItems = (dec as any).items ?? dec;
      setDecisions(Array.isArray(decItems) ? decItems : []);
    } catch {
      // Backend not running — use empty state
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // RCA polling
  useEffect(() => {
    if (!rcaPolling) return;
    const interval = setInterval(async () => {
      try {
        const result = await apiGet<RCAResult>(`/ops/rca/${rcaPolling}`);
        if (result.status === "completed") {
          setRcaResult(result);
          setRcaPolling(null);
        }
      } catch { /* still processing */ }
    }, 3000);
    return () => clearInterval(interval);
  }, [rcaPolling]);

  const triggerRca = async (incidentId: string) => {
    try {
      const job = await apiPost<{ job_id: string }>("/ops/rca/trigger", {
        incident_id: incidentId,
        tenant_id: "ott_co",
      });
      setRcaPolling(job.job_id);
    } catch { /* handle error */ }
  };

  /* ── FIX 6: Status update handler ── */
  const updateIncidentStatus = async (incidentId: string, newStatus: string) => {
    setStatusUpdating(true);
    try {
      await apiPatch(`/ops/incidents/${incidentId}/status`, { status: newStatus });
      if (selectedIncident) setSelectedIncident({ ...selectedIncident, status: newStatus as Incident["status"] });
      loadData();
    } catch { /* error */ }
    setStatusUpdating(false);
  };

  const filteredIncidents = incidents.filter((inc) => {
    if (severityFilter && inc.severity !== severityFilter) return false;
    if (statusFilter && inc.status !== statusFilter) return false;
    if (searchTerm && !inc.title.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  const filteredDecisions = decisions;

  /* ── FIX 2: Severity breakdown chart data ── */
  const sevBreakdown = dashboardRaw.severity_breakdown as Record<string, number> | undefined;
  const sevChartData = sevBreakdown
    ? Object.entries(sevBreakdown).map(([sev, count]) => ({ severity: sev, count, fill: SEV_BAR_COLORS[sev] || "#6b7280" }))
    : [];

  /* ── FIX 3: Incident trend chart data ── */
  const trendData = (dashboardRaw.incident_trend_24h as { hour: string; count: number }[]) ?? [];

  const TABS: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "Dashboard" },
    { key: "incidents", label: "Incidents" },
    { key: "rca", label: "RCA Explorer" },
    { key: "decisions", label: "Decision Log" },
    { key: "about", label: "About" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Ops Center</h2>

      {/* WebSocket toast */}
      {wsIncidents.length > 0 && (
        <div className="mb-4 px-4 py-2 rounded-lg border text-sm"
          style={{ backgroundColor: "var(--risk-high-bg)", borderColor: "var(--risk-high)", color: "var(--risk-high)" }}>
          {wsIncidents.length} new incident(s) via WebSocket
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Empty data state */}
      {!metrics && tab === "dashboard" && (
        <div className="flex flex-col items-center justify-center py-20">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
          <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>No data available</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>Connect a data source and run sync to populate this view.</p>
          <a href="/admin-governance" className="mt-3 text-xs px-3 py-1.5 rounded-lg" style={{ background: "var(--brand-primary)", color: "#fff" }}>Go to Data Sources →</a>
        </div>
      )}

      {/* ══════════ Tab: Dashboard ══════════ */}
      {tab === "dashboard" && (
        <div className="space-y-6">
          {/* FIX 1: KPI cards with correct fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Total Incidents" value={Number(dashboardRaw.total_incidents ?? 0)} />
            <MetricCard title="Open Now" value={metrics?.openIncidents ?? 0} />
            <MetricCard title="P50 MTTR" value={formatMTTR(metrics?.mttrP50 as number)} />
            <MetricCard title="Active P0" value={metrics?.p0Open ?? 0} />
          </div>

          {/* CDN + Infra + QoE from log data */}
          {dashboardRaw.cdn_health ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <h3 className="text-xs font-semibold mb-2" style={{ color: "var(--text-primary)" }}>CDN Health</h3>
                <p className="text-2xl font-bold" style={{ color: Number((dashboardRaw.cdn_health as {error_rate_pct: number}).error_rate_pct) > 5 ? "var(--status-error)" : "var(--risk-low)" }}>{String((dashboardRaw.cdn_health as {error_rate_pct: number}).error_rate_pct)}% err</p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{String((dashboardRaw.cdn_health as {cache_hit_rate_pct: number}).cache_hit_rate_pct)}% cache · {String((dashboardRaw.cdn_health as {bandwidth_gb: number}).bandwidth_gb)} GB</p>
              </div>
              <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <h3 className="text-xs font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Infrastructure</h3>
                <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{String((dashboardRaw.infrastructure as {avg_apdex: number} | undefined)?.avg_apdex ?? 0)} apdex</p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{String((dashboardRaw.infrastructure as {critical_services: string[]} | undefined)?.critical_services?.length ?? 0)} critical</p>
              </div>
              <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <h3 className="text-xs font-semibold mb-2" style={{ color: "var(--text-primary)" }}>QoE Score</h3>
                <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{String((dashboardRaw.qoe as {avg_score: number} | undefined)?.avg_score ?? 0)}</p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{String((dashboardRaw.qoe as {sessions_24h: number} | undefined)?.sessions_24h ?? 0)} sessions</p>
              </div>
            </div>
          ) : null}

          {/* FIX 2: Severity Breakdown + FIX 3: Incident Trend */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sevChartData.length > 0 && (
              <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <h3 className="text-xs font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Severity Breakdown</h3>
                <RechartsWrapper data={sevChartData} xKey="severity" yKey="count" title="" height={200} type="bar" />
              </div>
            )}
            {trendData.length > 0 && (
              <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <h3 className="text-xs font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Incident Trend (24h)</h3>
                <RechartsWrapper data={trendData} xKey="hour" yKey="count" title="" height={200} type="line" />
              </div>
            )}
          </div>

          {/* SLO Summary Widget */}
          <SLOSummaryWidget />
          <LiveAnomalyFeed />
        </div>
      )}

      {/* ══════════ Tab: Incidents ══════════ */}
      {tab === "incidents" && (
        <div>
          {/* Add Incident + Filters */}
          <div className="flex items-center justify-between mb-4">
            <button onClick={() => setShowAddIncident(true)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white"
              style={{ backgroundColor: "var(--brand-primary)" }}>
              + Add Incident
            </button>
          </div>

          {/* Add Incident Slide-over */}
          {showAddIncident && (
            <div className="fixed inset-0 z-50 flex">
              <div className="flex-1 bg-black/40" onClick={() => setShowAddIncident(false)} />
              <div className="w-96 h-full p-6 overflow-y-auto" style={{ backgroundColor: "var(--background-card)", borderLeft: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>New Incident</h3>
                  <button onClick={() => setShowAddIncident(false)} className="text-lg" style={{ color: "var(--text-muted)" }}>x</button>
                </div>
                <form onSubmit={async (e) => {
                  e.preventDefault(); setAddError(""); setAddLoading(true);
                  try {
                    await apiPost("/ops/incidents", { ...addForm, tenant_id: "ott_co" });
                    setShowAddIncident(false); setAddForm({ title: "", severity: "P2", description: "", affected_service: "" }); loadData();
                  } catch (err) { setAddError("Failed to create incident. Endpoint may not be available."); }
                  setAddLoading(false);
                }} className="space-y-4">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Title *</label>
                    <input required value={addForm.title} onChange={(e) => setAddForm({ ...addForm, title: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg text-sm border" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Severity *</label>
                    <select value={addForm.severity} onChange={(e) => setAddForm({ ...addForm, severity: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg text-sm border" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      <option value="P0">P0 — Critical</option><option value="P1">P1 — Major</option>
                      <option value="P2">P2 — Minor</option><option value="P3">P3 — Low</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Description</label>
                    <textarea value={addForm.description} onChange={(e) => setAddForm({ ...addForm, description: e.target.value })} rows={3}
                      className="w-full px-3 py-2 rounded-lg text-sm border resize-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Affected Service</label>
                    <input value={addForm.affected_service} onChange={(e) => setAddForm({ ...addForm, affected_service: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg text-sm border" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} placeholder="cdn, player, api..." />
                  </div>
                  {addError && <p className="text-xs text-red-400">{addError}</p>}
                  <button type="submit" disabled={addLoading} className="w-full py-2 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700">
                    {addLoading ? "Creating..." : "Create Incident"}
                  </button>
                </form>
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="flex gap-3 mb-4 flex-wrap">
            <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Severities</option>
              <option value="P0">P0</option><option value="P1">P1</option>
              <option value="P2">P2</option><option value="P3">P3</option>
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Statuses</option>
              <option value="open">Open</option><option value="investigating">Investigating</option>
              <option value="resolved">Resolved</option>
            </select>
            <input type="text" placeholder="Search incidents..." value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border flex-1 min-w-48"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
          </div>

          {/* FIX 8: Empty state */}
          {filteredIncidents.length === 0 ? (
            <div className="rounded-lg border p-12 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <div className="text-3xl mb-2" style={{ color: "var(--risk-low)" }}>&#10003;</div>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>No incidents found</p>
            </div>
          ) : (
            <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <LogTable
                columns={[
                  { key: "incidentId", label: "ID" },
                  { key: "title", label: "Title" },
                  { key: "severity", label: "Severity", render: (v) => <SevBadge severity={String(v)} /> },
                  { key: "status", label: "Status", render: (v) => <StatusDot status={String(v)} /> },
                  { key: "createdAt", label: "Created" },
                ]}
                data={filteredIncidents as unknown as Record<string, unknown>[]}
                onRowClick={(row) => setSelectedIncident(row as unknown as Incident)}
              />
            </div>
          )}

          {/* FIX 6: Incident Detail Dialog */}
          {selectedIncident && (
            <div className="fixed inset-0 z-50 flex items-center justify-center"
              style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => setSelectedIncident(null)}>
              <div className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-lg border p-6"
                style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
                onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>{selectedIncident.title}</h3>
                  <button onClick={() => setSelectedIncident(null)} style={{ color: "var(--text-muted)" }}>✕</button>
                </div>

                <div className="flex gap-2 mb-4">
                  <SevBadge severity={selectedIncident.severity} />
                  <StatusDot status={selectedIncident.status} />
                  {selectedIncident.mttrSeconds && (
                    <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--background)", color: "var(--text-secondary)" }}>
                      MTTR: {formatMTTR(selectedIncident.mttrSeconds)}
                    </span>
                  )}
                </div>

                <div className="space-y-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                  <p><strong>ID:</strong> <span className="font-mono">{selectedIncident.incidentId}</span></p>
                  <p><strong>Source:</strong> {selectedIncident.sourceApp || "—"}</p>
                  <p><strong>Created:</strong> {selectedIncident.createdAt}</p>

                  {/* Affected services as tags */}
                  {selectedIncident.affectedServices && selectedIncident.affectedServices.length > 0 && (
                    <div>
                      <strong>Affected Services:</strong>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {selectedIncident.affectedServices.map((svc, i) => (
                          <span key={i} className="text-xs px-2 py-0.5 rounded"
                            style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
                            {svc}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* TR summary card */}
                  {selectedIncident.summaryTr && (
                    <div className="rounded p-3" style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}>
                      <p className="text-xs font-semibold mb-1" style={{ color: "var(--text-muted)" }}>Turkce Ozet</p>
                      <p className="text-sm">{selectedIncident.summaryTr}</p>
                    </div>
                  )}

                  {/* EN detail card */}
                  {selectedIncident.detailEn && (
                    <div className="rounded p-3" style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}>
                      <p className="text-xs font-semibold mb-1" style={{ color: "var(--text-muted)" }}>Technical Detail</p>
                      <p className="text-sm font-mono">{selectedIncident.detailEn}</p>
                    </div>
                  )}

                  {/* Status update dropdown */}
                  <div className="flex items-center gap-3 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
                    <label className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Update Status:</label>
                    <select value={selectedIncident.status} disabled={statusUpdating}
                      onChange={(e) => updateIncidentStatus(selectedIncident.incidentId, e.target.value)}
                      className="text-sm px-2 py-1 rounded border"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      <option value="open">Open</option>
                      <option value="investigating">Investigating</option>
                      <option value="resolved">Resolved</option>
                    </select>
                  </div>

                  {/* HIGH risk actions */}
                  <div className="flex gap-2 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
                    <button className="px-3 py-1.5 rounded text-xs font-medium"
                      style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}
                      onClick={() => confirm("Execute remediation? This requires approval.") && setSelectedIncident(null)}>
                      Execute Remediation
                    </button>
                    <button className="px-3 py-1.5 rounded text-xs font-medium"
                      style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}
                      onClick={() => confirm("Escalate to on-call? This requires approval.") && setSelectedIncident(null)}>
                      Escalate to On-Call
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════════ Tab: RCA Explorer ══════════ */}
      {tab === "rca" && (
        <div className="space-y-4">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Root Cause Analysis for P0/P1 incidents</p>

          {/* Incident selector + trigger */}
          <div className="rounded-xl border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="flex items-center gap-3">
              <select value={rcaIncidentId} onChange={(e) => setRcaIncidentId(e.target.value)}
                className="flex-1 px-3 py-2 rounded-lg text-sm border"
                style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                <option value="">Select P0/P1 incident...</option>
                {incidents.filter((i) => i.severity === "P0" || i.severity === "P1").map((i) => (
                  <option key={i.incidentId} value={i.incidentId}>{i.incidentId} — [{i.severity}] {i.title}</option>
                ))}
              </select>
              <button onClick={async () => {
                if (!rcaIncidentId) return;
                setRcaLoading(true); setRcaData(null);
                try {
                  const result = await apiGet<Record<string, unknown>>(`/ops/incidents/${rcaIncidentId}/rca`);
                  setRcaData(result);
                } catch { setRcaData({ error: "RCA request failed" }); }
                setRcaLoading(false);
              }} disabled={!rcaIncidentId || rcaLoading}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ backgroundColor: "var(--brand-primary)" }}>
                {rcaLoading ? "Analyzing..." : "Trigger RCA"}
              </button>
            </div>
          </div>

          {/* RCA Result */}
          {rcaData && (
            <div className="rounded-xl border p-5" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              {rcaData.error ? (
                <p className="text-sm text-red-400">{String(rcaData.error)}</p>
              ) : rcaData.rca_available === false ? (
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>No RCA data available for this incident yet.</p>
              ) : (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>RCA Result</h4>
                  {rcaData.summary_tr && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{String(rcaData.summary_tr)}</p>}
                  {Array.isArray(rcaData.root_causes) && (
                    <div>
                      <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Root Causes</p>
                      {(rcaData.root_causes as string[]).map((c, i) => (
                        <p key={i} className="text-sm ml-2" style={{ color: "var(--text-secondary)" }}>- {c}</p>
                      ))}
                    </div>
                  )}
                  {Array.isArray(rcaData.timeline) && (
                    <div>
                      <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Timeline</p>
                      {(rcaData.timeline as { time: string; event: string }[]).map((t, i) => (
                        <p key={i} className="text-xs ml-2" style={{ color: "var(--text-muted)" }}>{t.time}: {t.event}</p>
                      ))}
                    </div>
                  )}
                  {Array.isArray(rcaData.recommended_actions) && (
                    <div>
                      <p className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Recommended Actions</p>
                      {(rcaData.recommended_actions as string[]).map((a, i) => (
                        <p key={i} className="text-sm ml-2" style={{ color: "var(--risk-medium)" }}>{i + 1}. {a}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ══════════ Tab: Decision Log ══════════ */}
      {tab === "decisions" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex gap-2">
              {(["1h", "6h", "24h", "7d"] as TimeRange[]).map((r) => (
                <button key={r} onClick={() => setTimeRange(r)}
                  className="px-3 py-1 rounded text-xs font-medium"
                  style={{
                    backgroundColor: timeRange === r ? "var(--brand-glow)" : "var(--background-card)",
                    color: timeRange === r ? "var(--brand-primary)" : "var(--text-secondary)",
                    border: "1px solid var(--border)",
                  }}>
                  {r}
                </button>
              ))}
            </div>
            <button onClick={() => exportToCsv(filteredDecisions as unknown as Record<string, unknown>[], "ops_decisions.csv")}
              className="px-3 py-1.5 rounded text-xs font-medium border"
              style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
              Export CSV
            </button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable
              columns={[
                { key: "createdAt", label: "Timestamp" },
                { key: "app", label: "Agent" },
                { key: "action", label: "Decision" },
                { key: "riskLevel", label: "Risk", render: (v) => <RiskBadge level={v as RiskLevel} /> },
                { key: "tenantId", label: "Tenant" },
                { key: "llmModelUsed", label: "Model" },
              ]}
              data={filteredDecisions as unknown as Record<string, unknown>[]}
            />
          </div>
        </div>
      )}

      {tab === "about" && <AboutTab />}

      <AgentChatPanel appName="Ops Center" />
    </div>
  );
}

// ── SLO Summary Widget ─────────────────────────────────────────

function SLOSummaryWidget() {
  const [met, setMet] = useState(0);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("aaop_token") || "" : "";
    const tid = typeof window !== "undefined" ? localStorage.getItem("aaop_tenant_id") || "ott_co" : "ott_co";
    const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${API}/slo/status`, {
      headers: { Authorization: `Bearer ${token}`, "X-Tenant-ID": tid },
    })
      .then((r) => r.json())
      .then((data: { is_met: boolean }[]) => {
        setTotal(data.length);
        setMet(data.filter((s) => s.is_met).length);
      })
      .catch(() => {});
  }, []);

  if (total === 0) return null;

  const allMet = met === total;
  return (
    <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
      <h3 className="text-xs font-semibold mb-2" style={{ color: "var(--text-primary)" }}>SLO Status</h3>
      <div className="text-2xl font-bold" style={{ color: allMet ? "var(--risk-low)" : "var(--risk-high)" }}>
        {met}/{total} SLO Met
      </div>
      <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
        {allMet ? "All targets within budget" : `${total - met} SLO breached`}
      </div>
    </div>
  );
}

// ── Live Anomaly Feed ──────────────────────────────────────────

function LiveAnomalyFeed() {
  const [anomalies, setAnomalies] = useState<Record<string, unknown>[]>([]);

  const fetchAnomalies = useCallback(async () => {
    try {
      const data = await apiGet<Record<string, unknown>[]>("/realtime/anomalies?minutes=60");
      setAnomalies(data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchAnomalies();
    const id = setInterval(fetchAnomalies, 30000);
    return () => clearInterval(id);
  }, [fetchAnomalies]);

  const sevColor: Record<string, string> = { P0: "var(--risk-high)", P1: "var(--risk-medium)", P2: "var(--risk-low)" };

  return (
    <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>Live Anomaly Feed</h3>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>{anomalies.length} anomalies (1h)</span>
      </div>
      {anomalies.length === 0 ? (
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>No anomalies detected</p>
      ) : (
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {anomalies.slice(0, 20).map((a, i) => (
            <div key={i} className="flex items-center gap-2 text-xs py-1 px-2 rounded"
              style={{ backgroundColor: "var(--background)" }}>
              <span className="font-mono font-bold" style={{ color: sevColor[String(a.severity)] || "var(--text-muted)" }}>
                {String(a.severity)}
              </span>
              <span style={{ color: "var(--text-secondary)" }}>{String(a.detector)}</span>
              <span style={{ color: "var(--text-muted)" }}>{String(a.metric)}: {String(a.current_value)}</span>
              <span className="ml-auto" style={{ color: "var(--text-muted)" }}>
                {String(a.detected_at).slice(11, 19)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AboutTab() {
  const sections = [
    { title: "Purpose", content: "Primary incident command interface. Correlates CDN, DRM, QoE, and live event signals to surface root causes faster than manual triage." },
    { title: "Key Features", items: ["Incident lifecycle (create→investigate→resolve)", "RCA Explorer with root cause analysis", "Decision Log with confidence scores", "Live Anomaly Feed (30s polling)", "SLO status widget"] },
    { title: "KPIs & Metrics", items: ["Active Incidents", "Open Now", "P50 MTTR", "Active P0", "CDN Error Rate", "Avg QoE Score"] },
    { title: "Use Cases", items: ["3am CDN spike: Anomaly fires → P1 surfaced → RCA correlates CDN + DRM → cache purge recommended", "Manual triage: Engineer creates P2 via Add Incident form", "Post-incident review: Lead audits LOW vs HIGH risk AI actions"] },
    { title: "AI Model", content: "P0/P1 → Opus · P2/P3 → Sonnet · RCA always Opus" },
  ];
  return (
    <div className="space-y-4 max-w-3xl">
      {sections.map((s) => (
        <div key={s.title} className="rounded-xl border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>{s.title}</h3>
          {s.content && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{s.content}</p>}
          {s.items && <ul className="space-y-1">{s.items.map((item, i) => <li key={i} className="text-sm" style={{ color: "var(--text-secondary)" }}>• {item}</li>)}</ul>}
        </div>
      ))}
    </div>
  );
}
