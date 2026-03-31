"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import SeverityBadge from "@/components/ui/SeverityBadge";
import LogTable from "@/components/ui/LogTable";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost, apiPatch } from "@/lib/api";
import { useAlertWebSocket } from "@/lib/socket";
import type { Alert, AlertRule, AlertChannel, SuppressionRule, SeverityLevel } from "@/types";

type Tab = "live" | "alerts" | "rules" | "channels" | "suppression" | "about";

export default function AlertCenter() {
  const [tab, setTab] = useState<Tab>("live");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [channels, setChannels] = useState<AlertChannel[]>([]);
  const [suppressions, setSuppressions] = useState<SuppressionRule[]>([]);
  const { alerts: wsAlerts, stormMode } = useAlertWebSocket();

  // Dialog state
  const [ackDialog, setAckDialog] = useState<Alert | null>(null);
  const [resolveDialog, setResolveDialog] = useState<Alert | null>(null);
  const [dialogNote, setDialogNote] = useState("");
  const [showNewRule, setShowNewRule] = useState(false);
  const [evalToast, setEvalToast] = useState("");
  const [newRule, setNewRule] = useState({ name: "", event_types: "", severity_min: "P3", channels: "slack", is_active: true });
  const [showNewSuppression, setShowNewSuppression] = useState(false);
  const [newSuppression, setNewSuppression] = useState({ name: "", start_time: "", end_time: "" });

  // Filters
  const [severityFilter, setSeverityFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const loadData = useCallback(async () => {
    try {
      const [aRes, r, c, s] = await Promise.all([
        apiGet<Record<string, unknown>>("/alerts/list?limit=50"),
        apiGet<AlertRule[]>("/alerts/rules"),
        apiGet<AlertChannel[]>("/alerts/channels"),
        apiGet<SuppressionRule[]>("/alerts/suppression").catch(() => []),
      ]);
      const items = (aRes as { items?: Alert[] }).items ?? (Array.isArray(aRes) ? aRes : []);
      setAlerts(items as Alert[]);
      setRules(Array.isArray(r) ? r : []);
      setChannels(Array.isArray(c) ? c : []);
      setSuppressions(Array.isArray(s) ? s : []);
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const acknowledgeAlert = async () => {
    if (!ackDialog) return;
    try {
      await apiPatch(`/alerts/${ackDialog.alertId}/acknowledge`, { ack_by: "admin", note: dialogNote });
      setAckDialog(null);
      setDialogNote("");
      loadData();
    } catch { /* error */ }
  };

  const resolveAlert = async () => {
    if (!resolveDialog) return;
    try {
      await apiPatch(`/alerts/${resolveDialog.alertId}/resolve`, { resolved_by: "admin", resolution: dialogNote });
      setResolveDialog(null);
      setDialogNote("");
      loadData();
    } catch { /* error */ }
  };

  const [ruleError, setRuleError] = useState("");
  const createRule = async () => {
    setRuleError("");
    try {
      await apiPost("/alerts/rules", {
        name: newRule.name,
        event_types: newRule.event_types ? newRule.event_types.split(",").map((s: string) => s.trim()) : [],
        severity_min: newRule.severity_min,
        channels: newRule.channels ? newRule.channels.split(",").map((s: string) => s.trim()) : ["slack"],
        is_active: newRule.is_active ? 1 : 0,
      });
      setShowNewRule(false);
      setNewRule({ name: "", event_types: "", severity_min: "P3", channels: "slack", is_active: true });
      loadData();
    } catch { setRuleError("Failed to create rule"); }
  };

  const [channelToast, setChannelToast] = useState("");
  const testChannel = async (channelType: string) => {
    setChannelToast(`Test for ${channelType} — not yet connected`);
    setTimeout(() => setChannelToast(""), 3000);
  };

  const filteredAlerts = alerts.filter((a) => {
    if (severityFilter && a.severity !== severityFilter) return false;
    if (statusFilter && a.status !== statusFilter) return false;
    return true;
  });

  const TABS: { key: Tab; label: string }[] = [
    { key: "live", label: "Live Feed" },
    { key: "alerts", label: "Alerts" },
    { key: "rules", label: "Rules" },
    { key: "channels", label: "Channels" },
    { key: "suppression", label: "Suppression" },
    { key: "about", label: "About" },
  ];

  const CHANNEL_TYPES: { type: string; icon: string }[] = [
    { type: "slack", icon: "💬" },
    { type: "pagerduty", icon: "📟" },
    { type: "email", icon: "📧" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Alert Center</h2>

      {/* Storm mode banner */}
      {stormMode && (
        <div className="mb-4 px-4 py-3 rounded-lg border" style={{ backgroundColor: "var(--risk-high-bg)", borderColor: "var(--risk-high)" }}>
          <span className="text-sm font-bold" style={{ color: "var(--risk-high)" }}>
            🔴 STORM MODE ACTIVE — &gt;20 alerts in 60s. Alerts being summarized.
          </span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>
            {t.label}
            {t.key === "live" && wsAlerts.length > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full text-xs" style={{ backgroundColor: "var(--risk-high)", color: "#fff" }}>{wsAlerts.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Empty data state */}
      {alerts.length === 0 && wsAlerts.length === 0 && tab === "live" && (
        <div className="flex flex-col items-center justify-center py-20">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
          <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>No data available</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>Connect a data source and run sync to populate this view.</p>
          <a href="/admin-governance" className="mt-3 text-xs px-3 py-1.5 rounded-lg" style={{ background: "var(--brand-primary)", color: "#fff" }}>Go to Data Sources →</a>
        </div>
      )}

      {/* Tab: Live Feed */}
      {tab === "live" && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <MetricCard title="Live Alerts" value={wsAlerts.length} trend="flat" />
            <MetricCard title="Total (DB)" value={alerts.length} trend="flat" />
            <MetricCard title="Rules Active" value={rules.filter((r) => r.isActive).length} trend="flat" />
            <MetricCard title="Storm Mode" value={stormMode ? "ON" : "OFF"} trend="flat" />
          </div>
          <div className="flex items-center gap-3 mb-4">
            <button onClick={async () => { try { const r = await apiPost("/alerts/evaluate", {}); const msg = `Evaluated: ${(r as Record<string,unknown>).evaluated}, Routed: ${(r as Record<string,unknown>).routed}`; setEvalToast(msg); setTimeout(() => setEvalToast(""), 3000); } catch {} }} className="px-4 py-1.5 rounded text-sm font-medium text-white" style={{ background: "var(--brand-primary)" }}>Evaluate Now</button>
            {evalToast && <span className="text-xs px-3 py-1 rounded-full" style={{ backgroundColor: "rgba(34,197,94,0.15)", color: "#22c55e" }}>{evalToast}</span>}
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="max-h-96 overflow-y-auto">
              {wsAlerts.length === 0 && (
                <div className="p-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>
                  Listening for alerts via WebSocket... No alerts yet.
                </div>
              )}
              {wsAlerts.map((a, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-2" style={{ borderBottom: "1px solid var(--border)" }}>
                  <div className="flex items-center gap-3">
                    <SeverityBadge severity={(a.severity || "P3") as SeverityLevel} />
                    <span className="text-sm" style={{ color: "var(--text-primary)" }}>{a.title}</span>
                  </div>
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>{a.sentAt}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Alerts */}
      {tab === "alerts" && (
        <div>
          <div className="flex gap-3 mb-4 flex-wrap">
            <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Severities</option>
              {["P0", "P1", "P2", "P3"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Statuses</option>
              {["active", "acknowledged", "resolved"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable
              columns={[
                { key: "sentAt", label: "Timestamp" },
                { key: "severity", label: "Severity", render: (v) => <SeverityBadge severity={v as SeverityLevel} /> },
                { key: "title", label: "Title" },
                { key: "channel", label: "Channel" },
                { key: "status", label: "Status" },
                { key: "actions", label: "Actions", render: (_, row) => (
                  <div className="flex gap-1">
                    <button onClick={(e) => { e.stopPropagation(); setAckDialog(row as unknown as Alert); }}
                      className="text-xs px-2 py-0.5 rounded border" style={{ borderColor: "var(--border)", color: "var(--risk-medium)" }}>Ack</button>
                    <button onClick={(e) => { e.stopPropagation(); setResolveDialog(row as unknown as Alert); }}
                      className="text-xs px-2 py-0.5 rounded border" style={{ borderColor: "var(--border)", color: "var(--risk-low)" }}>Resolve</button>
                  </div>
                )},
              ]}
              data={filteredAlerts as unknown as Record<string, unknown>[]}
            />
          </div>
        </div>
      )}

      {/* Tab: Rules */}
      {tab === "rules" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{rules.length} rule(s)</p>
            <button onClick={() => setShowNewRule(true)}
              className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>+ New Rule</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable
              columns={[
                { key: "name", label: "Name" },
                { key: "eventTypes", label: "Event Types" },
                { key: "severityMin", label: "Min Severity" },
                { key: "channels", label: "Channels" },
                { key: "isActive", label: "Active", render: (v) => (
                  <span className="text-xs" style={{ color: v ? "var(--risk-low)" : "var(--text-muted)" }}>{v ? "● Active" : "● Inactive"}</span>
                )},
              ]}
              data={rules as unknown as Record<string, unknown>[]}
            />
          </div>

          {showNewRule && (
            <div className="fixed inset-0 z-50 flex justify-end" style={{ backgroundColor: "rgba(0,0,0,0.5)" }} onClick={() => setShowNewRule(false)}>
              <div className="w-96 h-full p-6 overflow-y-auto" style={{ backgroundColor: "var(--background-card)" }} onClick={(e) => e.stopPropagation()}>
                <h3 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>New Alert Rule</h3>
                <div className="space-y-4">
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Rule Name</label>
                    <input type="text" value={newRule.name} onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                      className="w-full text-sm px-3 py-2 rounded border outline-none"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Event Types</label>
                    <select value={newRule.event_types} onChange={(e) => setNewRule({ ...newRule, event_types: e.target.value })}
                      className="w-full text-sm px-3 py-2 rounded border"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      <option value="">Select...</option>
                      <option value="cdn_anomaly_detected">cdn_anomaly_detected</option>
                      <option value="incident_created">incident_created</option>
                      <option value="qoe_degradation">qoe_degradation</option>
                      <option value="churn_risk_detected">churn_risk_detected</option>
                      <option value="scale_recommendation">scale_recommendation</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Min Severity</label>
                    <select value={newRule.severity_min} onChange={(e) => setNewRule({ ...newRule, severity_min: e.target.value })}
                      className="w-full text-sm px-3 py-2 rounded border"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      {["P0", "P1", "P2", "P3"].map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Channel</label>
                    <select value={newRule.channels} onChange={(e) => setNewRule({ ...newRule, channels: e.target.value })}
                      className="w-full text-sm px-3 py-2 rounded border"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      <option value="slack">Slack</option>
                      <option value="pagerduty">PagerDuty</option>
                      <option value="email">Email</option>
                    </select>
                  </div>
                  {ruleError && <p className="text-xs text-red-400">{ruleError}</p>}
                  <div className="flex gap-2 pt-4">
                    <button onClick={createRule} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Create</button>
                    <button onClick={() => { setShowNewRule(false); setRuleError(""); }} className="px-4 py-2 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Channels */}
      {tab === "channels" && (
        <div>
          {channelToast && <div className="mb-4 px-3 py-2 rounded-lg text-xs" style={{ backgroundColor: "rgba(234,179,8,0.1)", color: "#eab308" }}>{channelToast}</div>}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {CHANNEL_TYPES.map((ct) => {
              const ch = channels.find((c) => (c as Record<string, unknown>).channel_type === ct.type || c.channelType === ct.type);
              return (
                <div key={ct.type} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{ct.icon}</span>
                      <span className="text-sm font-semibold capitalize" style={{ color: "var(--text-primary)" }}>{ct.type}</span>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded"
                      style={{ backgroundColor: ch ? "rgba(34,197,94,0.15)" : "rgba(72,79,88,0.15)", color: ch ? "#22c55e" : "var(--text-muted)" }}>
                      {ch ? "Configured" : "Not configured"}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button className="text-xs px-3 py-1.5 rounded border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                      title="Configuration coming soon">Configure</button>
                    <button onClick={() => testChannel(ct.type)} className="text-xs px-3 py-1.5 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>Test</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab: Suppression */}
      {tab === "suppression" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{suppressions.length} maintenance window(s)</p>
            <button onClick={() => setShowNewSuppression(true)} className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>+ Add Window</button>
          </div>

          {/* Weekly grid placeholder */}
          <div className="rounded-lg border p-4 mb-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <h4 className="text-xs font-semibold mb-3" style={{ color: "var(--text-muted)" }}>This Week</h4>
            <div className="grid grid-cols-7 gap-1">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                <div key={d} className="text-center">
                  <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{d}</p>
                  <div className="h-16 rounded" style={{ backgroundColor: "var(--background-hover)" }} />
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable
              columns={[
                { key: "name", label: "Name" },
                { key: "startTime", label: "Start" },
                { key: "endTime", label: "End" },
                { key: "isActive", label: "Active", render: (v) => <span style={{ color: v ? "var(--risk-low)" : "var(--text-muted)" }}>{v ? "● Yes" : "● No"}</span> },
              ]}
              data={suppressions as unknown as Record<string, unknown>[]}
            />
          </div>

          {showNewSuppression && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.5)" }} onClick={() => setShowNewSuppression(false)}>
              <div className="w-96 rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
                <h3 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Add Maintenance Window</h3>
                <div className="space-y-4">
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Name</label>
                    <input type="text" value={newSuppression.name} onChange={(e) => setNewSuppression({ ...newSuppression, name: e.target.value })}
                      className="w-full text-sm px-3 py-2 rounded border outline-none"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Start Time</label>
                    <input type="datetime-local" value={newSuppression.start_time} onChange={(e) => setNewSuppression({ ...newSuppression, start_time: e.target.value })}
                      className="w-full text-sm px-3 py-2 rounded border outline-none"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>End Time</label>
                    <input type="datetime-local" value={newSuppression.end_time} onChange={(e) => setNewSuppression({ ...newSuppression, end_time: e.target.value })}
                      className="w-full text-sm px-3 py-2 rounded border outline-none"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div className="flex gap-2 pt-2">
                    <button onClick={async () => {
                      try {
                        await apiPost("/alerts/suppression", { name: newSuppression.name, start_time: newSuppression.start_time, end_time: newSuppression.end_time, is_active: 1 });
                        setShowNewSuppression(false); setNewSuppression({ name: "", start_time: "", end_time: "" }); loadData();
                      } catch { /* error */ }
                    }} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Create</button>
                    <button onClick={() => setShowNewSuppression(false)} className="px-4 py-2 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Ack/Resolve dialogs */}
      {(ackDialog || resolveDialog) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
          onClick={() => { setAckDialog(null); setResolveDialog(null); setDialogNote(""); }}>
          <div className="w-96 rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
              {ackDialog ? "Acknowledge Alert" : "Resolve Alert"}
            </h3>
            <p className="text-sm mb-3" style={{ color: "var(--text-secondary)" }}>
              {(ackDialog ?? resolveDialog)?.title}
            </p>
            <textarea
              value={dialogNote}
              onChange={(e) => setDialogNote(e.target.value)}
              placeholder={ackDialog ? "Add a note..." : "Resolution details..."}
              className="w-full text-sm px-3 py-2 rounded border outline-none mb-4 h-24 resize-none"
              style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}
            />
            <div className="flex gap-2">
              <button onClick={ackDialog ? acknowledgeAlert : resolveAlert}
                className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
                {ackDialog ? "Acknowledge" : "Resolve"}
              </button>
              <button onClick={() => { setAckDialog(null); setResolveDialog(null); setDialogNote(""); }}
                className="px-4 py-2 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {tab === "about" && <AboutTab />}

      <AgentChatPanel appName="Alert Center" />
    </div>
  );
}

function AboutTab() {
  const sections = [
    { title: "Purpose", content: "Prevents alert fatigue via AI deduplication, storm detection, and smart routing before any notification reaches a human." },
    { title: "Key Features", items: ["Live Feed (WebSocket)", "Alert list with ack/resolve", "Routing rules engine", "Slack/PagerDuty/Email channels", "Storm mode (>10 alerts/5min)", "Maintenance windows", "15min Redis dedup"] },
    { title: "KPIs & Metrics", items: ["Live Alerts", "Total Alerts (DB)", "Active Rules", "Storm Mode status"] },
    { title: "Use Cases", items: ["Match day storm: 40 alerts in 2min → storm mode → one consolidated P1", "Maintenance window: Weekly backup → P3 alerts suppressed", "Rule tuning: qoe_degradation P2 → Email only"] },
    { title: "AI Model", content: "Routing → Haiku · Message generation → Sonnet" },
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
