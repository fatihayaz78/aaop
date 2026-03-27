"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost, apiPatch, exportToCsv } from "@/lib/api";
import type { AdminDashboard, Tenant, AuditEntry } from "@/types/admin_governance";

type Tab = "dashboard" | "tenants" | "modules" | "audit" | "compliance" | "usage" | "datasources";

const planColor: Record<string, { bg: string; text: string }> = {
  enterprise: { bg: "rgba(168,85,247,0.15)", text: "#a855f7" },
  pro: { bg: "rgba(59,130,246,0.15)", text: "#3b82f6" },
  starter: { bg: "rgba(156,163,175,0.15)", text: "#9ca3af" },
};
const compColor = (s: number) => s >= 90 ? "var(--risk-low)" : s >= 70 ? "var(--risk-medium)" : "var(--risk-high)";
const fmtNum = (n: number) => n >= 1e6 ? `${(n/1e6).toFixed(1)}M` : n >= 1e3 ? `${(n/1e3).toFixed(1)}K` : String(n);

const ALL_APPS = ["ops_center", "log_analyzer", "alert_center", "viewer_experience", "live_intelligence", "growth_retention", "capacity_cost", "admin_governance", "ai_lab", "knowledge_base", "devops_assistant"];

export default function AdminGovernance() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [dash, setDash] = useState<AdminDashboard | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [compliance, setCompliance] = useState<Record<string, unknown> | null>(null);
  const [usage, setUsage] = useState<Record<string, unknown> | null>(null);
  const [modules, setModules] = useState<Record<string, unknown>[]>([]);
  const [selectedTenant, setSelectedTenant] = useState("s_sport_plus");
  const [auditTenantFilter, setAuditTenantFilter] = useState("");
  const [auditActionFilter, setAuditActionFilter] = useState("");
  const [auditStatusFilter, setAuditStatusFilter] = useState("");
  const [showNewTenant, setShowNewTenant] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPlan, setNewPlan] = useState("starter");
  const [reportMsg, setReportMsg] = useState("");

  const loadDash = useCallback(async () => { try { setDash(await apiGet<AdminDashboard>("/admin/dashboard")); } catch { /* */ } }, []);
  const loadTenants = useCallback(async () => { try { setTenants(await apiGet<Tenant[]>("/admin/tenants")); } catch { /* */ } }, []);

  useEffect(() => { loadDash(); loadTenants(); }, [loadDash, loadTenants]);
  useEffect(() => {
    if (tab === "dashboard") { const i = setInterval(loadDash, 60000); return () => clearInterval(i); }
    if (tab === "audit") {
      (async () => {
        let url = "/admin/audit?limit=50";
        if (auditTenantFilter) url += `&tenant_id=${auditTenantFilter}`;
        if (auditActionFilter) url += `&action=${auditActionFilter}`;
        if (auditStatusFilter) url += `&status=${auditStatusFilter}`;
        try { const r = await apiGet<{ items: AuditEntry[]; total: number }>(url); setAudit(r.items ?? []); setAuditTotal(r.total ?? 0); } catch { /* */ }
      })();
    }
    if (tab === "compliance") { (async () => { try { setCompliance(await apiGet("/admin/compliance")); } catch { /* */ } })(); }
    if (tab === "usage") { (async () => { try { setUsage(await apiGet("/admin/usage")); } catch { /* */ } })(); }
    if (tab === "modules") { (async () => { try { setModules(await apiGet(`/admin/tenants/${selectedTenant}/modules`)); } catch { /* */ } })(); }
  }, [tab, auditTenantFilter, auditActionFilter, auditStatusFilter, selectedTenant, loadDash]);

  const toggleModule = async (appName: string, enabled: boolean) => {
    await apiPatch(`/admin/tenants/${selectedTenant}/modules`, { app_name: appName, enabled });
    try { setModules(await apiGet(`/admin/tenants/${selectedTenant}/modules`)); } catch { /* */ }
  };

  const createTenant = async () => {
    if (!newName) return;
    await apiPost("/admin/tenants", { name: newName, plan: newPlan });
    setNewName(""); setShowNewTenant(false); loadTenants();
  };

  const enabledApps = modules.filter((m) => m.is_enabled === 1 || m.is_enabled === true);

  const TABS: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "Dashboard" }, { key: "tenants", label: "Tenants" },
    { key: "modules", label: "Module Config" }, { key: "audit", label: "Audit Log" },
    { key: "compliance", label: "Compliance" }, { key: "usage", label: "Usage Stats" },
    { key: "datasources", label: "Data Sources" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Admin & Governance</h2>
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

      {/* ═══ Dashboard ═══ */}
      {tab === "dashboard" && dash && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Active Tenants" value={dash.active_tenants} />
            <MetricCard title="Audit Events 24h" value={dash.audit_events_24h} />
            <MetricCard title="Failed Actions" value={dash.failed_actions_24h} />
            <MetricCard title="Compliance Score" value={`${dash.compliance_score}%`} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[{ label: "Input Tokens", val: dash.token_usage_today.input },
              { label: "Output Tokens", val: dash.token_usage_today.output },
              { label: "Cost Today", val: `$${dash.token_usage_today.cost_usd.toFixed(2)}` }].map((c) => (
              <div key={c.label} className="rounded-lg border p-3 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{c.label}</p>
                <p className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>{typeof c.val === "number" ? fmtNum(c.val) : c.val}</p>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={dash.top_actions} xKey="action" yKey="count" title="Top Actions" height={200} type="bar" />
            </div>
            <div className="rounded-lg border p-4 flex justify-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <div className="relative w-40 h-40">
                <svg viewBox="0 0 100 100" className="w-full h-full">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border)" strokeWidth="8" />
                  <circle cx="50" cy="50" r="42" fill="none" stroke={compColor(dash.compliance_score)}
                    strokeWidth="8" strokeDasharray={`${(dash.compliance_score / 100) * 264} 264`}
                    strokeLinecap="round" transform="rotate(-90 50 50)" />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold" style={{ color: compColor(dash.compliance_score) }}>{dash.compliance_score}</span>
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>Compliance</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Tenants ═══ */}
      {tab === "tenants" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{tenants.length} tenant(s)</p>
            <button onClick={() => setShowNewTenant(!showNewTenant)} className="px-3 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Add Tenant</button>
          </div>
          {showNewTenant && (
            <div className="rounded-lg border p-4 mb-4 flex gap-3 items-end" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Name</label>
                <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} className="text-sm px-3 py-1.5 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} /></div>
              <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Plan</label>
                <select value={newPlan} onChange={(e) => setNewPlan(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                  <option value="starter">Starter</option><option value="pro">Pro</option><option value="enterprise">Enterprise</option>
                </select></div>
              <button onClick={createTenant} className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Create</button>
            </div>
          )}
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "name", label: "Name" },
              { key: "plan", label: "Plan", render: (v) => { const c = planColor[String(v)] || planColor.starter; return <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: c.bg, color: c.text }}>{String(v)}</span>; }},
              { key: "is_active", label: "Status", render: (v) => <span className="text-xs" style={{ color: v ? "var(--risk-low)" : "var(--risk-high)" }}>{v ? "active" : "suspended"}</span> },
              { key: "created_at", label: "Created", render: (v) => <span className="text-xs">{String(v ?? "").slice(0, 16)}</span> },
            ]} data={tenants as unknown as Record<string, unknown>[]} />
          </div>
        </div>
      )}

      {/* ═══ Module Config ═══ */}
      {tab === "modules" && (
        <div>
          <div className="flex gap-3 mb-4 items-center">
            <select value={selectedTenant} onChange={(e) => setSelectedTenant(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              {tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>{enabledApps.length} / 11 modules active</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {ALL_APPS.map((app) => {
              const mod = modules.find((m) => m.module_name === app);
              const enabled = mod ? (mod.is_enabled === 1 || mod.is_enabled === true) : false;
              return (
                <div key={app} className="rounded-lg border p-3 flex items-center justify-between" style={{ backgroundColor: "var(--background-card)", borderColor: enabled ? "var(--risk-low)" : "var(--border)" }}>
                  <span className="text-sm" style={{ color: "var(--text-primary)" }}>{app.replace(/_/g, " ")}</span>
                  <button onClick={() => toggleModule(app, !enabled)} className="relative w-10 h-5 rounded-full transition-colors" style={{ backgroundColor: enabled ? "var(--brand-primary)" : "var(--border)" }}>
                    <span className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform" style={{ left: enabled ? "calc(100% - 18px)" : "2px" }} />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ═══ Audit Log ═══ */}
      {tab === "audit" && (
        <div>
          <div className="flex gap-3 mb-4 flex-wrap">
            <select value={auditTenantFilter} onChange={(e) => setAuditTenantFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Tenants</option>
              {tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <select value={auditActionFilter} onChange={(e) => setAuditActionFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Actions</option>
              {["login", "logout", "create_incident", "update_status", "trigger_rca", "export_data", "update_config", "view_dashboard"].map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            <select value={auditStatusFilter} onChange={(e) => setAuditStatusFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Status</option><option value="success">Success</option><option value="failed">Failed</option>
            </select>
            <button onClick={() => exportToCsv(audit as unknown as Record<string, unknown>[], "audit_log.csv")} className="px-3 py-1.5 rounded text-xs border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Export CSV</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "created_at", label: "Time", render: (v) => <span className="text-xs">{String(v).slice(0, 19)}</span> },
              { key: "tenant_id", label: "Tenant" },
              { key: "user_id", label: "User", render: (v) => <span className="font-mono text-xs">{String(v).slice(0, 10)}</span> },
              { key: "action", label: "Action" },
              { key: "resource", label: "Resource" },
              { key: "status", label: "Status", render: (v) => {
                const s = String(v);
                return <span className="inline-flex items-center gap-1 text-xs"><span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: s === "success" ? "#4ade80" : "#f87171" }} />{s}</span>;
              }},
            ]} data={audit as unknown as Record<string, unknown>[]} />
          </div>
          <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>{auditTotal} total entries</p>
        </div>
      )}

      {/* ═══ Compliance ═══ */}
      {tab === "compliance" && compliance && (() => {
        const score = Number((compliance as any).overall_score ?? 0);
        const checks = ((compliance as any).checks ?? []) as { name: string; status: string; description: string; last_checked: string }[];
        const violations = ((compliance as any).violations ?? []) as { rule: string; tenant_id: string; description: string; severity: string }[];
        return (
          <div className="space-y-6">
            <div className="rounded-lg border p-6 text-center" style={{ backgroundColor: score >= 90 ? "rgba(34,197,94,0.1)" : "rgba(234,179,8,0.1)", borderColor: compColor(score) }}>
              <p className="text-4xl font-bold" style={{ color: compColor(score) }}>{score}%</p>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>Overall Compliance Score</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {checks.map((c) => (
                <div key={c.name} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: c.status === "pass" ? "#22c55e" : c.status === "warning" ? "#eab308" : "#ef4444" }}>
                  <div className="flex items-center gap-2 mb-1">
                    <span style={{ color: c.status === "pass" ? "#22c55e" : c.status === "warning" ? "#eab308" : "#ef4444" }}>{c.status === "pass" ? "\u2713" : c.status === "warning" ? "\u26A0" : "\u2717"}</span>
                    <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{c.name}</span>
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{c.description}</p>
                  <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>Checked: {c.last_checked?.slice(11, 19)}</p>
                </div>
              ))}
            </div>
            {violations.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--risk-medium)" }}>Violations ({violations.length})</h3>
                {violations.map((v, i) => (
                  <div key={i} className="rounded border p-3 mb-2" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: v.severity === "medium" ? "var(--risk-medium-bg)" : "var(--risk-low-bg)", color: v.severity === "medium" ? "var(--risk-medium)" : "var(--risk-low)" }}>{v.severity}</span>
                      <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>{v.rule}</span>
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>({v.tenant_id})</span>
                    </div>
                    <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{v.description}</p>
                  </div>
                ))}
              </div>
            )}
            <button onClick={() => { setReportMsg(`Report generated at ${new Date().toISOString().slice(0, 19)}`); setTimeout(() => setReportMsg(""), 5000); }}
              className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Generate Report</button>
            {reportMsg && <p className="text-xs" style={{ color: "var(--risk-low)" }}>{reportMsg}</p>}
          </div>
        );
      })()}

      {/* ═══ Usage Stats ═══ */}
      {tab === "usage" && usage && (() => {
        const u = usage as any;
        const topModel = (u.cost_by_model ?? []).sort((a: any, b: any) => b.cost_usd - a.cost_usd)[0];
        const topApp = (u.cost_by_app ?? []).sort((a: any, b: any) => b.cost_usd - a.cost_usd)[0];
        return (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <MetricCard title="Total Cost (7d)" value={`$${Number(u.total_cost_7d ?? 0).toFixed(2)}`} />
              <MetricCard title="Top Model" value={topModel?.model?.split("-").slice(1, 2).join("") ?? "—"} />
              <MetricCard title="Top App" value={topApp?.app ?? "—"} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <RechartsWrapper data={u.cost_by_model ?? []} xKey="model" yKey="cost_usd" title="Cost by Model" height={200} type="bar" />
              </div>
              <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <RechartsWrapper data={u.cost_by_app ?? []} xKey="app" yKey="cost_usd" title="Cost by App" height={200} type="bar" />
              </div>
            </div>
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={u.daily_cost_7d ?? []} xKey="date" yKey="cost_usd" title="Daily Cost (7d)" height={200} type="line" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border p-4 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Input Tokens Total</p>
                <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{fmtNum(u.token_breakdown?.input_total ?? 0)}</p>
              </div>
              <div className="rounded-lg border p-4 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Output Tokens Total</p>
                <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{fmtNum(u.token_breakdown?.output_total ?? 0)}</p>
              </div>
            </div>
          </div>
        );
      })()}

      {tab === "datasources" && <DataSourcesTab />}

      <AgentChatPanel appName="Admin & Governance" />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// DATA SOURCES TAB
// ══════════════════════════════════════════════════════════════════════

const DS_API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SRC_CATEGORIES: Record<string, string> = {
  medianova: "CDN", origin_server: "CDN",
  widevine_drm: "DRM", fairplay_drm: "DRM",
  player_events: "QoE", npaw_analytics: "QoE",
  api_logs: "Platform", newrelic_apm: "Platform",
  crm_subscriber: "Business", epg: "Business", billing: "Business",
  push_notifications: "Business", app_reviews: "Business",
};
const CAT_COLORS: Record<string, { bg: string; color: string }> = {
  CDN: { bg: "rgba(31,111,235,0.15)", color: "#1f6feb" },
  DRM: { bg: "rgba(210,153,34,0.15)", color: "#d29922" },
  QoE: { bg: "rgba(35,134,54,0.15)", color: "#238636" },
  Platform: { bg: "rgba(139,148,158,0.15)", color: "#8b949e" },
  Business: { bg: "rgba(218,54,51,0.15)", color: "#da3633" },
};
const INTERVALS = [
  { value: "", label: "Manual" }, { value: "5", label: "Every 5 min" },
  { value: "60", label: "Every hour" }, { value: "360", label: "Every 6h" },
  { value: "1440", label: "Every 24h" },
];

function DataSourcesTab() {
  const [configs, setConfigs] = useState<Record<string, unknown>[]>([]);
  const [statuses, setStatuses] = useState<Record<string, unknown>[]>([]);
  const [editing, setEditing] = useState<Record<string, unknown> | null>(null);
  const [syncing, setSyncing] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState<Set<string>>(new Set());
  const [importResult, setImportResult] = useState<Record<string, string>>({});
  const [watchStatus, setWatchStatus] = useState<{ watching: boolean; folders: { folder: string; source_name: string; exists: boolean; file_count: number }[] } | null>(null);

  const load = useCallback(() => {
    fetch(`${DS_API}/data-sources/configs?tenant_id=aaop_company`).then(r => r.json()).then(setConfigs).catch(() => {});
    fetch(`${DS_API}/data-sources/sync-status?tenant_id=aaop_company`).then(r => r.json()).then(setStatuses).catch(() => {});
    fetch(`${DS_API}/data-sources/watch-status?tenant_id=aaop_company`).then(r => r.json()).then(setWatchStatus).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSync = async (configId: string) => {
    setSyncing(prev => { const n = new Set(Array.from(prev)); n.add(configId); return n; });
    try {
      await fetch(`${DS_API}/data-sources/sync/${configId}`, { method: "POST" });
    } catch { /* */ }
    setSyncing(prev => { const n = new Set(Array.from(prev)); n.delete(configId); return n; });
    load();
  };

  const handleSyncAll = async () => {
    await fetch(`${DS_API}/data-sources/sync-all?tenant_id=aaop_company`, { method: "POST" });
    load();
  };

  const handleImportDelete = async (configId: string) => {
    setImporting(prev => { const n = new Set(Array.from(prev)); n.add(configId); return n; });
    try {
      const res = await fetch(`${DS_API}/data-sources/import-delete/${configId}`, { method: "POST" });
      const data = await res.json();
      setImportResult(prev => ({ ...prev, [configId]: `${data.rows_inserted || 0} rows imported, ${data.files_deleted || 0} files deleted` }));
    } catch { setImportResult(prev => ({ ...prev, [configId]: "Error" })); }
    setImporting(prev => { const n = new Set(Array.from(prev)); n.delete(configId); return n; });
    load();
  };

  const handleSave = async () => {
    if (!editing) return;
    await fetch(`${DS_API}/data-sources/configs/${editing.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(editing),
    });
    setEditing(null);
    load();
  };

  const activeCount = configs.filter(c => c.enabled).length;
  const lastSync = configs.reduce((acc: string, c: Record<string, unknown>) => {
    const ls = c.last_sync_at as string | null;
    if (ls && (!acc || ls > acc)) return ls;
    return acc;
  }, "");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Data Sources</h3>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>{activeCount} sources active{lastSync ? ` · last sync ${lastSync.slice(11, 16)} UTC` : ""}</p>
        </div>
        <button onClick={handleSyncAll} className="px-4 py-2 rounded-lg text-sm text-white" style={{ background: "var(--brand-primary)" }}>Sync All</button>
      </div>

      {/* Watch status */}
      {watchStatus && (
        <div className="rounded-lg p-3" style={{ background: "var(--background-card)", border: "1px solid var(--border)" }}>
          <div className="flex items-center gap-2 mb-2">
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: watchStatus.watching ? "var(--status-active)" : "var(--status-inactive)" }} />
            <span className="text-sm" style={{ color: "var(--text-primary)" }}>Watcher: {watchStatus.watching ? "Active" : "Inactive"}</span>
            {watchStatus.folders.filter(f => f.file_count > 0).length > 0 && (
              <span className="text-xs px-2 py-0.5 rounded" style={{ background: "var(--risk-medium-bg)", color: "var(--risk-medium)" }}>
                {watchStatus.folders.reduce((s, f) => s + f.file_count, 0)} files pending
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {watchStatus.folders.filter(f => f.file_count > 0).map(f => (
              <span key={f.folder} className="text-xs px-2 py-0.5 rounded" style={{ background: "var(--background-hover)", color: "var(--text-secondary)" }}>
                {f.folder}: {f.file_count}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Source cards grid */}
      <div className="grid grid-cols-2 gap-3">
        {configs.map((c: Record<string, unknown>) => {
          const cat = SRC_CATEGORIES[c.source_name as string] || "Platform";
          const cc = CAT_COLORS[cat] || CAT_COLORS.Platform;
          const enabled = Boolean(c.enabled);
          const isSyncing = syncing.has(c.id as string);
          return (
            <div key={c.id as string} className="rounded-lg p-3" style={{ background: "var(--background-card)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2 mb-1">
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: enabled ? "var(--status-active)" : "var(--status-inactive)" }} />
                <span className="text-sm" style={{ color: "var(--text-primary)", fontWeight: 500 }}>{c.source_name as string}</span>
                <span className="text-xs px-1.5 py-0.5 rounded ml-auto" style={{ background: cc.bg, color: cc.color }}>{cat}</span>
              </div>
              <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>
                {c.last_sync_rows ? `${c.last_sync_rows} rows` : "No data"} · {c.source_type as string}
              </p>
              <p className="text-xs mb-2 truncate" style={{ color: "var(--text-muted)", maxWidth: 250 }}>
                {(c.local_path || c.s3_bucket || "Not configured") as string}
              </p>
              {/* Watch indicator */}
              {(() => {
                const wf = watchStatus?.folders.find(f => f.source_name === c.source_name);
                if (!wf) return null;
                if (wf.exists && wf.file_count > 0) return <p className="text-xs mb-1" style={{ color: "var(--risk-medium)" }}>{wf.file_count} files pending</p>;
                if (wf.exists) return <p className="text-xs mb-1" style={{ color: "var(--status-active)" }}>Watching</p>;
                return <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>Folder not found</p>;
              })()}
              <div className="flex gap-2">
                <button onClick={() => handleSync(c.id as string)} disabled={isSyncing} className="text-xs px-2 py-1 rounded disabled:opacity-50" style={{ background: "var(--brand-glow)", color: "var(--brand-primary)" }}>
                  {isSyncing ? "Syncing..." : "Sync"}
                </button>
                <button onClick={() => handleImportDelete(c.id as string)} disabled={importing.has(c.id as string)} className="text-xs px-2 py-1 rounded disabled:opacity-50" style={{ background: "var(--background-hover)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                  {importing.has(c.id as string) ? "Importing..." : "Import & Delete"}
                </button>
                <button onClick={() => setEditing({ ...c })} className="text-xs px-2 py-1 rounded" style={{ background: "var(--background-hover)", color: "var(--text-secondary)" }}>Configure</button>
              </div>
              {importResult[c.id as string] && <p className="text-xs mt-1" style={{ color: "var(--risk-low)" }}>{importResult[c.id as string]}</p>}
            </div>
          );
        })}
      </div>

      {/* Config panel */}
      {editing && (
        <div className="rounded-lg p-4" style={{ background: "var(--background-card)", border: "1px solid var(--border)" }}>
          <h4 className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>Configure: {editing.source_name as string}</h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs block mb-1" style={{ color: "var(--text-secondary)" }}>Source Type</label>
              <select value={editing.source_type as string} onChange={e => setEditing({ ...editing, source_type: e.target.value })} className="w-full px-2 py-1.5 rounded text-sm" style={{ background: "var(--background-hover)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                <option value="local">Local</option><option value="s3">S3</option>
              </select>
            </div>
            <div>
              <label className="text-xs block mb-1" style={{ color: "var(--text-secondary)" }}>Sync Interval</label>
              <select value={String(editing.sync_interval_minutes ?? "")} onChange={e => setEditing({ ...editing, sync_interval_minutes: e.target.value ? Number(e.target.value) : null })} className="w-full px-2 py-1.5 rounded text-sm" style={{ background: "var(--background-hover)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                {INTERVALS.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
              </select>
            </div>
            {editing.source_type === "local" && (
              <div className="col-span-2">
                <label className="text-xs block mb-1" style={{ color: "var(--text-secondary)" }}>Local Path</label>
                <input value={(editing.local_path || "") as string} onChange={e => setEditing({ ...editing, local_path: e.target.value })} className="w-full px-2 py-1.5 rounded text-sm" style={{ background: "var(--background-hover)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
              </div>
            )}
            {editing.source_type === "s3" && (<>
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-secondary)" }}>S3 Bucket</label>
                <input value={(editing.s3_bucket || "") as string} onChange={e => setEditing({ ...editing, s3_bucket: e.target.value })} className="w-full px-2 py-1.5 rounded text-sm" style={{ background: "var(--background-hover)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-secondary)" }}>S3 Prefix</label>
                <input value={(editing.s3_prefix || "") as string} onChange={e => setEditing({ ...editing, s3_prefix: e.target.value })} className="w-full px-2 py-1.5 rounded text-sm" style={{ background: "var(--background-hover)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
              </div>
            </>)}
            <div>
              <label className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                <input type="checkbox" checked={Boolean(editing.enabled)} onChange={e => setEditing({ ...editing, enabled: e.target.checked })} />
                Enabled
              </label>
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <button onClick={handleSave} className="px-3 py-1.5 rounded text-sm text-white" style={{ background: "var(--brand-primary)" }}>Save</button>
            <button onClick={() => setEditing(null)} className="px-3 py-1.5 rounded text-sm" style={{ background: "var(--background-hover)", color: "var(--text-secondary)" }}>Cancel</button>
          </div>
          {editing.last_sync_error ? <p className="text-xs mt-2" style={{ color: "var(--status-error)" }}>Last error: {String(editing.last_sync_error)}</p> : null}
        </div>
      )}

      {/* Sync status table */}
      {statuses.length > 0 && (
        <div className="rounded-lg overflow-hidden" style={{ background: "var(--background-card)", border: "1px solid var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--background-hover)", color: "var(--text-secondary)" }}>
                <th className="text-left px-3 py-2">Source</th>
                <th className="text-left px-3 py-2">Type</th>
                <th className="text-right px-3 py-2">Last Sync Rows</th>
                <th className="text-left px-3 py-2">Last Sync</th>
                <th className="text-left px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {statuses.map((s: Record<string, unknown>) => (
                <tr key={s.source_name as string} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>{s.source_name as string}</td>
                  <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{s.source_type as string}</td>
                  <td className="px-3 py-2 text-right" style={{ color: "var(--text-secondary)" }}>{(s.last_sync_rows ?? "—") as string}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: "var(--text-muted)" }}>{(s.last_sync_at ?? "Never") as string}</td>
                  <td className="px-3 py-2">
                    <span className="text-xs px-1.5 py-0.5 rounded" style={{
                      background: s.enabled ? "var(--risk-low-bg)" : "rgba(139,148,158,0.15)",
                      color: s.enabled ? "var(--risk-low)" : "var(--text-muted)",
                    }}>{s.enabled ? "Active" : "Disabled"}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
