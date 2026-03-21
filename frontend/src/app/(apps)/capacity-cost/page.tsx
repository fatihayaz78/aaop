"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import RiskBadge from "@/components/ui/RiskBadge";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet } from "@/lib/api";

type Tab = "forecast" | "usage" | "jobs" | "cost" | "thresholds";
type Horizon = "7d" | "14d" | "30d";

function usagePctColor(pct: number): string {
  if (pct >= 90) return "var(--risk-high)";
  if (pct >= 70) return "var(--risk-medium)";
  return "var(--risk-low)";
}

export default function CapacityCost() {
  const [tab, setTab] = useState<Tab>("forecast");
  const [horizon, setHorizon] = useState<Horizon>("7d");
  const [selectedJob, setSelectedJob] = useState<Record<string, unknown> | null>(null);

  // Auto-refresh usage every 30s
  useEffect(() => {
    if (tab !== "usage") return;
    const iv = setInterval(() => { /* refresh */ }, 30000);
    return () => clearInterval(iv);
  }, [tab]);

  const TABS: { key: Tab; label: string }[] = [
    { key: "forecast", label: "Capacity Forecast" },
    { key: "usage", label: "Current Usage" },
    { key: "jobs", label: "Automation Jobs" },
    { key: "cost", label: "Cost Analysis" },
    { key: "thresholds", label: "Thresholds" },
  ];

  const RESOURCES = [
    { name: "CPU", pct: 42 },
    { name: "Memory", pct: 68 },
    { name: "Bandwidth", pct: 35 },
    { name: "Storage", pct: 55 },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Capacity & Cost</h2>
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>{t.label}</button>
        ))}
      </div>

      {tab === "forecast" && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <MetricCard title="Current CPU" value="42" unit="%" trend="flat" />
            <MetricCard title="Current Memory" value="68" unit="%" trend="up" delta="+3% vs yesterday" />
            <MetricCard title="Predicted Peak (24h)" value="78" unit="%" trend="up" delta="Growing" />
          </div>
          <div className="flex gap-2 mb-4">
            {(["7d", "14d", "30d"] as Horizon[]).map((h) => (
              <button key={h} onClick={() => setHorizon(h)} className="px-3 py-1 rounded text-xs font-medium"
                style={{ backgroundColor: horizon === h ? "var(--brand-glow)" : "var(--background-card)", color: horizon === h ? "var(--brand-primary)" : "var(--text-secondary)", border: "1px solid var(--border)" }}>{h}</button>
            ))}
          </div>
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <RechartsWrapper data={[]} xKey="date" yKey="pct" title={`Capacity Forecast (${horizon})`} color="var(--brand-primary)" />
          </div>
        </div>
      )}

      {tab === "usage" && (
        <div>
          <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>Auto-refresh: 30s</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {RESOURCES.map((r) => (
              <div key={r.name} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{r.name}</span>
                  <span className="text-sm font-bold" style={{ color: usagePctColor(r.pct) }}>{r.pct}%</span>
                </div>
                <div className="w-full h-3 rounded-full" style={{ backgroundColor: "var(--border)" }}>
                  <div className="h-3 rounded-full transition-all" style={{ width: `${r.pct}%`, backgroundColor: usagePctColor(r.pct) }} />
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "service", label: "Service" }, { key: "cpu", label: "CPU %" }, { key: "memory", label: "Memory %" }, { key: "status", label: "Status" },
            ]} data={[]} />
          </div>
        </div>
      )}

      {tab === "jobs" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Automation jobs</p>
            <button onClick={() => confirm("Create automation job? HIGH risk action.")} className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>Create Job (Approval Required)</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "jobId", label: "Job ID" },
              { key: "type", label: "Type" },
              { key: "status", label: "Status", render: (v) => {
                const colors: Record<string, string> = { queued: "var(--text-muted)", running: "var(--brand-primary)", success: "var(--risk-low)", failed: "var(--risk-high)" };
                return <span className="text-xs font-medium" style={{ color: colors[v as string] ?? "var(--text-muted)" }}>● {String(v)}</span>;
              }},
              { key: "createdAt", label: "Created" },
              { key: "duration", label: "Duration" },
            ]} data={[]} onRowClick={(row) => setSelectedJob(row)} />
          </div>
          {selectedJob && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => setSelectedJob(null)}>
              <div className="w-full max-w-lg rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
                <div className="flex justify-between mb-4">
                  <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Job Detail</h3>
                  <button onClick={() => setSelectedJob(null)} style={{ color: "var(--text-muted)" }}>✕</button>
                </div>
                <pre className="text-xs p-3 rounded overflow-auto max-h-64" style={{ backgroundColor: "var(--background)", color: "var(--text-secondary)" }}>
                  {JSON.stringify(selectedJob, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "cost" && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <MetricCard title="LLM Cost Today" value="—" unit="USD" trend="flat" />
            <MetricCard title="LLM Cost 7d" value="—" unit="USD" trend="flat" />
            <MetricCard title="Storage Cost" value="—" unit="USD" trend="flat" />
            <MetricCard title="Est. Monthly" value="—" unit="USD" trend="flat" />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={[]} xKey="app" yKey="tokens" title="LLM Token Usage by App (7d)" type="bar" color="var(--brand-primary)" />
            </div>
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={[]} xKey="category" yKey="cost" title="Cost Breakdown" type="bar" color="var(--brand-accent)" />
            </div>
          </div>
        </div>
      )}

      {tab === "thresholds" && (
        <div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "resource", label: "Resource" },
              { key: "warn", label: "Warn %", render: (v) => <span className="text-sm font-mono" style={{ color: "var(--risk-medium)" }}>{String(v)}%</span> },
              { key: "critical", label: "Critical %", render: (v) => <span className="text-sm font-mono" style={{ color: "var(--risk-high)" }}>{String(v)}%</span> },
              { key: "action", label: "", render: () => <button className="text-xs px-2 py-0.5 rounded border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Edit</button> },
            ]} data={[
              { resource: "CPU", warn: 70, critical: 90 },
              { resource: "Memory", warn: 70, critical: 90 },
              { resource: "Bandwidth", warn: 70, critical: 90 },
              { resource: "Storage", warn: 70, critical: 90 },
            ]} />
          </div>
        </div>
      )}

      <AgentChatPanel appName="Capacity & Cost" />
    </div>
  );
}
