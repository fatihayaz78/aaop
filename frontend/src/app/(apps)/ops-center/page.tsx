"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import RiskBadge from "@/components/ui/RiskBadge";
import SeverityBadge from "@/components/ui/SeverityBadge";
import LogTable from "@/components/ui/LogTable";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost, exportToCsv } from "@/lib/api";
import { useOpsWebSocket } from "@/lib/socket";
import type { Incident, OpsMetrics, AgentDecision, RCAResult, SeverityLevel, RiskLevel } from "@/types";

type Tab = "dashboard" | "incidents" | "rca" | "decisions";
type TimeRange = "1h" | "6h" | "24h" | "7d";

export default function OpsCenter() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [severityFilter, setSeverityFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [timeRange, setTimeRange] = useState<TimeRange>("24h");
  const [rcaPolling, setRcaPolling] = useState<string | null>(null);
  const [rcaResult, setRcaResult] = useState<RCAResult | null>(null);
  const { incidents: wsIncidents } = useOpsWebSocket();

  const loadData = useCallback(async () => {
    try {
      const [m, inc, dec] = await Promise.all([
        apiGet<OpsMetrics>("/ops/dashboard?tenant_id=bein_sports"),
        apiGet<Incident[]>("/ops/incidents?tenant_id=bein_sports&limit=50"),
        apiGet<AgentDecision[]>("/ops/health").then(() => [] as AgentDecision[]).catch(() => []),
      ]);
      setMetrics(m);
      setIncidents(inc);
      setDecisions(dec);
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
        tenant_id: "bein_sports",
      });
      setRcaPolling(job.job_id);
    } catch { /* handle error */ }
  };

  const filteredIncidents = incidents.filter((inc) => {
    if (severityFilter && inc.severity !== severityFilter) return false;
    if (statusFilter && inc.status !== statusFilter) return false;
    if (searchTerm && !inc.title.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  const filteredDecisions = decisions; // time range filter would apply here with real data

  const TABS: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "Dashboard" },
    { key: "incidents", label: "Incidents" },
    { key: "rca", label: "RCA Explorer" },
    { key: "decisions", label: "Decision Log" },
  ];

  return (
    <div>
      {/* Breadcrumb title */}
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>
        Ops Center
      </h2>

      {/* WebSocket toast for new P0/P1 */}
      {wsIncidents.length > 0 && (
        <div
          className="mb-4 px-4 py-2 rounded-lg border text-sm"
          style={{
            backgroundColor: "var(--risk-high-bg)",
            borderColor: "var(--risk-high)",
            color: "var(--risk-high)",
          }}
        >
          🔴 {wsIncidents.length} new incident(s) via WebSocket
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{
              borderColor: tab === t.key ? "var(--brand-primary)" : "transparent",
              color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Dashboard */}
      {tab === "dashboard" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard title="Open Incidents" value={metrics?.openIncidents ?? 0} trend="flat" />
          <MetricCard title="MTTR P50" value={metrics?.mttrP50 ?? "—"} unit="min" trend="flat" />
          <MetricCard title="Active Tenants" value={metrics?.activeTenants ?? 0} trend="flat" />
          <MetricCard title="Agent Decisions 24h" value={metrics?.decisionsLast24h ?? 0} trend="flat" />
        </div>
      )}

      {/* Tab: Incidents */}
      {tab === "incidents" && (
        <div>
          {/* Filters */}
          <div className="flex gap-3 mb-4 flex-wrap">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}
            >
              <option value="">All Severities</option>
              <option value="P0">P0</option>
              <option value="P1">P1</option>
              <option value="P2">P2</option>
              <option value="P3">P3</option>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}
            >
              <option value="">All Statuses</option>
              <option value="open">Open</option>
              <option value="investigating">Investigating</option>
              <option value="resolved">Resolved</option>
            </select>
            <input
              type="text"
              placeholder="Search incidents..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border flex-1 min-w-48"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}
            />
          </div>

          {/* Table */}
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable
              columns={[
                { key: "incidentId", label: "ID" },
                { key: "title", label: "Title" },
                { key: "severity", label: "Severity", render: (v) => <SeverityBadge severity={v as SeverityLevel} /> },
                { key: "status", label: "Status" },
                { key: "tenantId", label: "Tenant" },
                { key: "createdAt", label: "Created" },
              ]}
              data={filteredIncidents as unknown as Record<string, unknown>[]}
              onRowClick={(row) => setSelectedIncident(row as unknown as Incident)}
            />
          </div>

          {/* Detail Dialog */}
          {selectedIncident && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center"
              style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
              onClick={() => setSelectedIncident(null)}
            >
              <div
                className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-lg border p-6"
                style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
                    {selectedIncident.title}
                  </h3>
                  <button onClick={() => setSelectedIncident(null)} className="text-sm" style={{ color: "var(--text-muted)" }}>✕</button>
                </div>
                <div className="space-y-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                  <div className="flex gap-2">
                    <SeverityBadge severity={selectedIncident.severity} />
                    <span>{selectedIncident.status}</span>
                  </div>
                  <p><strong>ID:</strong> {selectedIncident.incidentId}</p>
                  <p><strong>Source:</strong> {selectedIncident.sourceApp ?? "—"}</p>
                  <p><strong>Tenant:</strong> {selectedIncident.tenantId}</p>
                  {selectedIncident.summaryTr && <p><strong>Özet (TR):</strong> {selectedIncident.summaryTr}</p>}
                  {selectedIncident.detailEn && <p><strong>Detail (EN):</strong> {selectedIncident.detailEn}</p>}
                  <p><strong>Created:</strong> {selectedIncident.createdAt}</p>
                  {selectedIncident.affectedServices && (
                    <p><strong>Affected:</strong> {selectedIncident.affectedServices.join(", ")}</p>
                  )}
                  {/* HIGH risk actions */}
                  <div className="flex gap-2 mt-4 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
                    <button
                      className="px-3 py-1.5 rounded text-xs font-medium"
                      style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}
                      onClick={() => confirm("Execute remediation? This requires approval.") && setSelectedIncident(null)}
                    >
                      Execute Remediation
                    </button>
                    <button
                      className="px-3 py-1.5 rounded text-xs font-medium"
                      style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}
                      onClick={() => confirm("Escalate to on-call? This requires approval.") && setSelectedIncident(null)}
                    >
                      Escalate to On-Call
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: RCA Explorer */}
      {tab === "rca" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              RCA decisions for P0/P1 incidents
            </p>
            {rcaPolling && (
              <span className="text-sm animate-pulse" style={{ color: "var(--brand-primary)" }}>
                ⏳ RCA in progress...
              </span>
            )}
          </div>

          {rcaResult && (
            <div
              className="rounded-lg border p-4 mb-4"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
            >
              <h4 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
                RCA Result: {rcaResult.rcaId}
              </h4>
              <p className="text-sm mb-1" style={{ color: "var(--text-secondary)" }}>
                <strong>Root Cause:</strong> {rcaResult.rootCause}
              </p>
              <p className="text-sm mb-1" style={{ color: "var(--text-secondary)" }}>
                <strong>Confidence:</strong> {(rcaResult.confidenceScore * 100).toFixed(0)}%
              </p>
              {rcaResult.remediationPlan && (
                <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  <strong>Plan:</strong> {rcaResult.remediationPlan}
                </p>
              )}
            </div>
          )}

          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              No RCA results yet. Trigger RCA from an incident to see results.
            </p>
            <button
              onClick={() => triggerRca("INC-DEMO-001")}
              disabled={!!rcaPolling}
              className="mt-3 px-4 py-2 rounded text-sm font-medium disabled:opacity-50"
              style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}
            >
              Trigger RCA (Demo)
            </button>
          </div>
        </div>
      )}

      {/* Tab: Decision Log */}
      {tab === "decisions" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex gap-2">
              {(["1h", "6h", "24h", "7d"] as TimeRange[]).map((r) => (
                <button
                  key={r}
                  onClick={() => setTimeRange(r)}
                  className="px-3 py-1 rounded text-xs font-medium"
                  style={{
                    backgroundColor: timeRange === r ? "var(--brand-glow)" : "var(--background-card)",
                    color: timeRange === r ? "var(--brand-primary)" : "var(--text-secondary)",
                    border: "1px solid var(--border)",
                  }}
                >
                  {r}
                </button>
              ))}
            </div>
            <button
              onClick={() => exportToCsv(filteredDecisions as unknown as Record<string, unknown>[], "ops_decisions.csv")}
              className="px-3 py-1.5 rounded text-xs font-medium border"
              style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
            >
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

      <AgentChatPanel appName="Ops Center" />
    </div>
  );
}
