"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import RiskBadge from "@/components/ui/RiskBadge";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost, apiPatch, apiDelete, exportToCsv } from "@/lib/api";
import type { RiskLevel } from "@/types";

type Tab = "tenants" | "modules" | "keys" | "audit" | "compliance" | "usage";
type AuditRange = "1h" | "24h" | "7d" | "30d";

const APPS_LIST = ["ops_center", "log_analyzer", "alert_center", "viewer_experience", "live_intelligence", "growth_retention", "capacity_cost", "admin_governance", "ai_lab", "knowledge_base", "devops_assistant"];

export default function AdminGovernance() {
  const [tab, setTab] = useState<Tab>("tenants");
  const [role] = useState("admin"); // Would come from JWT
  const [tenants, setTenants] = useState<Record<string, unknown>[]>([]);
  const [auditLog, setAuditLog] = useState<Record<string, unknown>[]>([]);
  const [auditRange, setAuditRange] = useState<AuditRange>("24h");
  const [showNewTenant, setShowNewTenant] = useState(false);
  const [newTenant, setNewTenant] = useState({ id: "", name: "", plan: "starter" });
  const [showRotateConfirm, setShowRotateConfirm] = useState<string | null>(null);
  const [rotatedKey, setRotatedKey] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([
        apiGet<Record<string, unknown>[]>("/admin/tenants"),
        apiGet<Record<string, unknown>[]>("/admin/audit?tenant_id=bein_sports&limit=100"),
      ]);
      setTenants(t);
      setAuditLog(a);
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  if (role !== "admin") {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-lg font-bold mb-2" style={{ color: "var(--risk-high)" }}>Access Denied</p>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Admin role required. Current role: {role}</p>
        </div>
      </div>
    );
  }

  const createTenant = async () => {
    try {
      await apiPost("/admin/tenants", { tenant_id: newTenant.id, name: newTenant.name, plan: newTenant.plan });
      setShowNewTenant(false);
      setNewTenant({ id: "", name: "", plan: "starter" });
      loadData();
    } catch {}
  };

  const deleteTenant = async (id: string) => {
    if (!confirm("This will delete all tenant data. Are you sure? HIGH risk action.")) return;
    try { await apiDelete(`/admin/tenants/${id}`); loadData(); } catch {}
  };

  const TABS: { key: Tab; label: string }[] = [
    { key: "tenants", label: "Tenants" },
    { key: "modules", label: "Module Config" },
    { key: "keys", label: "API Keys" },
    { key: "audit", label: "Audit Log" },
    { key: "compliance", label: "Compliance" },
    { key: "usage", label: "Usage Stats" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Admin & Governance</h2>
      <div className="flex gap-1 mb-6 border-b overflow-x-auto" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>{t.label}</button>
        ))}
      </div>

      {/* Tenants */}
      {tab === "tenants" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{tenants.length} tenant(s)</p>
            <button onClick={() => setShowNewTenant(true)} className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>+ New Tenant</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "tenantId", label: "Tenant ID" }, { key: "name", label: "Name" }, { key: "plan", label: "Plan" },
              { key: "isActive", label: "Status", render: (v) => <span style={{ color: v ? "var(--risk-low)" : "var(--text-muted)" }}>{v ? "● Active" : "● Inactive"}</span> },
              { key: "createdAt", label: "Created" },
              { key: "actions", label: "Actions", render: (_, row) => (
                <div className="flex gap-1">
                  <button className="text-xs px-2 py-0.5 rounded border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Edit</button>
                  <button onClick={(e) => { e.stopPropagation(); deleteTenant(row.tenantId as string); }} className="text-xs px-2 py-0.5 rounded" style={{ color: "var(--risk-high)" }}>Delete</button>
                </div>
              )},
            ]} data={tenants} />
          </div>
          {showNewTenant && (
            <div className="fixed inset-0 z-50 flex justify-end" style={{ backgroundColor: "rgba(0,0,0,0.5)" }} onClick={() => setShowNewTenant(false)}>
              <div className="w-96 h-full p-6" style={{ backgroundColor: "var(--background-card)" }} onClick={(e) => e.stopPropagation()}>
                <h3 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>New Tenant</h3>
                <div className="space-y-4">
                  <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Tenant ID</label>
                    <input type="text" value={newTenant.id} onChange={(e) => setNewTenant({...newTenant, id: e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} placeholder="my_company" /></div>
                  <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Name</label>
                    <input type="text" value={newTenant.name} onChange={(e) => setNewTenant({...newTenant, name: e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} /></div>
                  <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Plan</label>
                    <select value={newTenant.plan} onChange={(e) => setNewTenant({...newTenant, plan: e.target.value})} className="w-full text-sm px-3 py-2 rounded border" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      <option value="starter">Starter</option><option value="growth">Growth</option><option value="enterprise">Enterprise</option>
                    </select></div>
                  <div className="flex gap-2 pt-4">
                    <button onClick={createTenant} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Create</button>
                    <button onClick={() => setShowNewTenant(false)} className="px-4 py-2 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Module Config */}
      {tab === "modules" && (
        <div className="rounded-lg border overflow-x-auto" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th className="text-left px-3 py-2 text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Tenant</th>
                {APPS_LIST.map((a) => (
                  <th key={a} className="text-center px-2 py-2 text-xs font-semibold" style={{ color: "var(--text-muted)" }}>{a.replace(/_/g, " ").slice(0, 8)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(tenants.length > 0 ? tenants : [{ tenantId: "bein_sports" }]).map((t, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>{String(t.tenantId ?? t.tenant_id ?? "—")}</td>
                  {APPS_LIST.map((a) => (
                    <td key={a} className="text-center px-2 py-2">
                      <button className="w-8 h-4 rounded-full relative" style={{ backgroundColor: "var(--risk-low)" }}>
                        <span className="absolute right-0.5 top-0.5 w-3 h-3 rounded-full bg-white" />
                      </button>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* API Keys */}
      {tab === "keys" && (
        <div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "keyName", label: "Key Name" },
              { key: "maskedValue", label: "Value", render: (v) => <span className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>{String(v ?? "sk-ant-...****")}</span> },
              { key: "createdAt", label: "Created" },
              { key: "lastUsed", label: "Last Used" },
              { key: "actions", label: "Actions", render: (_, row) => (
                <button onClick={(e) => { e.stopPropagation(); setShowRotateConfirm(row.keyName as string); }}
                  className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>Rotate</button>
              )},
            ]} data={[{ keyName: "anthropic", maskedValue: "sk-ant-...ab3f", createdAt: "2026-03-01", lastUsed: "2026-03-21" }]} />
          </div>
          {showRotateConfirm && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => { setShowRotateConfirm(null); setRotatedKey(null); }}>
              <div className="w-96 rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
                <h3 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Rotate API Key</h3>
                <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>Rotate key &quot;{showRotateConfirm}&quot;? This action requires approval.</p>
                {rotatedKey ? (
                  <div className="p-3 rounded mb-4" style={{ backgroundColor: "var(--risk-low-bg)" }}>
                    <p className="text-xs font-semibold mb-1" style={{ color: "var(--risk-low)" }}>New key (one-time display):</p>
                    <p className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>{rotatedKey}</p>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button onClick={() => setRotatedKey("sk-ant-...x7q2")} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--risk-high)", color: "#fff" }}>Confirm Rotate</button>
                    <button onClick={() => setShowRotateConfirm(null)} className="px-4 py-2 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Audit Log */}
      {tab === "audit" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex gap-2">
              {(["1h", "24h", "7d", "30d"] as AuditRange[]).map((r) => (
                <button key={r} onClick={() => setAuditRange(r)} className="px-3 py-1 rounded text-xs font-medium"
                  style={{ backgroundColor: auditRange === r ? "var(--brand-glow)" : "var(--background-card)", color: auditRange === r ? "var(--brand-primary)" : "var(--text-secondary)", border: "1px solid var(--border)" }}>{r}</button>
              ))}
            </div>
            <button onClick={() => confirm("Export audit log? HIGH risk action.") && exportToCsv(auditLog, "audit_log.csv")}
              className="text-xs px-3 py-1.5 rounded" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>Export (Approval Required)</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "created_at", label: "Timestamp" }, { key: "user_id", label: "User" }, { key: "action", label: "Action" }, { key: "resource", label: "Resource" },
              { key: "success", label: "Result", render: (v) => <span style={{ color: v ? "var(--risk-low)" : "var(--risk-high)" }}>{v ? "✓ Success" : "✗ Failed"}</span> },
            ]} data={auditLog} />
          </div>
        </div>
      )}

      {/* Compliance */}
      {tab === "compliance" && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <MetricCard title="HIGH Risk Approvals" value="0" trend="flat" />
            <MetricCard title="Unapproved Executions" value="0" trend="flat" />
            <MetricCard title="FP Rate" value="—" unit="%" trend="flat" />
            <MetricCard title="SLA Breaches" value="0" trend="flat" />
          </div>
          <div className="flex justify-end mb-4">
            <button className="text-xs px-3 py-1.5 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>Generate Report</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "timestamp", label: "Time" }, { key: "module", label: "Module" }, { key: "tool", label: "Tool" },
              { key: "riskLevel", label: "Risk", render: (v) => <RiskBadge level={v as RiskLevel} /> },
              { key: "outcome", label: "Outcome" }, { key: "agent", label: "Agent" },
            ]} data={[]} />
          </div>
        </div>
      )}

      {/* Usage Stats */}
      {tab === "usage" && (
        <div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={[]} xKey="app" yKey="decisions" title="Agent Decisions by App (7d)" type="bar" color="var(--brand-primary)" />
            </div>
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={[]} xKey="date" yKey="tokens" title="Token Usage Trend (30d)" color="var(--brand-accent)" />
            </div>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "appName", label: "App" }, { key: "decisions24h", label: "Decisions 24h" }, { key: "avgLatencyMs", label: "Avg Latency" }, { key: "errorRate", label: "Error Rate" }, { key: "modelMix", label: "Model Mix" },
            ]} data={[]} />
          </div>
        </div>
      )}

      <AgentChatPanel appName="Admin & Governance" />
    </div>
  );
}
