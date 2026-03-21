"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import RiskBadge from "@/components/ui/RiskBadge";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost } from "@/lib/api";

type Tab = "experiments" | "models" | "prompts" | "evals" | "cost";

const APPS_LIST = ["ops_center","log_analyzer","alert_center","viewer_experience","live_intelligence","growth_retention","capacity_cost","admin_governance","ai_lab","knowledge_base","devops_assistant"];

export default function AILab() {
  const [tab, setTab] = useState<Tab>("experiments");
  const [experiments, setExperiments] = useState<Record<string, unknown>[]>([]);
  const [models, setModels] = useState<Record<string, unknown>[]>([]);
  const [selectedExp, setSelectedExp] = useState<Record<string, unknown> | null>(null);
  const [showNewExp, setShowNewExp] = useState(false);
  const [newExp, setNewExp] = useState({ name: "", model_a: "sonnet", model_b: "haiku", metric: "", sample_size: "500" });
  const [promptApp, setPromptApp] = useState("ops_center");
  const [promptType, setPromptType] = useState("system");
  const [evalPolling, setEvalPolling] = useState<string | null>(null);
  const [budgetPct, setBudgetPct] = useState(0);

  const loadData = useCallback(async () => {
    try {
      const [e, m] = await Promise.all([
        apiGet<Record<string, unknown>[]>("/ai-lab/experiments?tenant_id=bein_sports"),
        apiGet<Record<string, unknown>[]>("/ai-lab/models?tenant_id=bein_sports"),
      ]);
      setExperiments(e); setModels(m);
    } catch {}
  }, []);
  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!evalPolling) return;
    const iv = setInterval(async () => {
      try { const r = await apiGet<{ status: string }>(`/ai-lab/evaluations/${evalPolling}`);
        if (r.status === "completed" || r.status === "failed") setEvalPolling(null);
      } catch {}
    }, 5000);
    return () => clearInterval(iv);
  }, [evalPolling]);

  const budgetColor = budgetPct > 95 ? "var(--risk-high)" : budgetPct > 80 ? "var(--risk-medium)" : "var(--risk-low)";

  const TABS: { key: Tab; label: string }[] = [
    { key: "experiments", label: "Experiments" }, { key: "models", label: "Model Registry" },
    { key: "prompts", label: "Prompt Lab" }, { key: "evals", label: "Evaluations" }, { key: "cost", label: "Cost Tracker" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>AI Lab</h2>
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>{t.label}</button>
        ))}
      </div>

      {tab === "experiments" && (<div>
        <div className="flex justify-between mb-4">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{experiments.length} experiment(s)</p>
          <button onClick={() => setShowNewExp(true)} className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>+ New Experiment</button>
        </div>
        <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <LogTable columns={[
            { key: "experimentId", label: "ID" }, { key: "name", label: "Name" },
            { key: "status", label: "Status", render: (v) => {
              const c = v === "completed" ? "var(--risk-low)" : v === "failed" ? "var(--risk-high)" : "var(--brand-primary)";
              return <span className="text-xs font-medium" style={{ color: c }}>{v === "running" ? "● Running" : `● ${String(v)}`}</span>;
            }},
            { key: "metric", label: "Metric" }, { key: "pValue", label: "p-value", render: (v) => {
              const p = v as number; return p != null ? <span style={{ color: p < 0.05 ? "var(--risk-low)" : "var(--text-muted)" }}>{p.toFixed(4)}</span> : <span style={{ color: "var(--text-muted)" }}>—</span>;
            }},
          ]} data={experiments} onRowClick={(row) => setSelectedExp(row)} />
        </div>
        {selectedExp && (
          <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => setSelectedExp(null)}>
            <div className="w-full max-w-lg rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between mb-4"><h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Experiment Results</h3><button onClick={() => setSelectedExp(null)} style={{ color: "var(--text-muted)" }}>✕</button></div>
              <div className="space-y-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                <p><strong>Name:</strong> {String(selectedExp.name)}</p>
                <p><strong>p-value:</strong> <span style={{ color: (selectedExp.pValue as number) < 0.05 ? "var(--risk-low)" : "var(--text-muted)" }}>{String(selectedExp.pValue ?? "—")}</span></p>
                <p><strong>Winner:</strong> {(selectedExp.pValue as number) < 0.05 ? "Model A" : "Inconclusive"}</p>
              </div>
            </div>
          </div>
        )}
        {showNewExp && (
          <div className="fixed inset-0 z-50 flex justify-end" style={{ backgroundColor: "rgba(0,0,0,0.5)" }} onClick={() => setShowNewExp(false)}>
            <div className="w-96 h-full p-6 overflow-y-auto" style={{ backgroundColor: "var(--background-card)" }} onClick={(e) => e.stopPropagation()}>
              <h3 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>New Experiment</h3>
              <div className="space-y-3">
                {[{l:"Name",k:"name",t:"text"},{l:"Model A",k:"model_a",t:"select",o:["haiku","sonnet","opus"]},{l:"Model B",k:"model_b",t:"select",o:["haiku","sonnet","opus"]},{l:"Metric",k:"metric",t:"text"},{l:"Sample Size",k:"sample_size",t:"number"}].map((f) => (
                  <div key={f.k}><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>{f.l}</label>
                    {f.t === "select" ? <select value={(newExp as Record<string,string>)[f.k]} onChange={(e) => setNewExp({...newExp, [f.k]: e.target.value})} className="w-full text-sm px-3 py-2 rounded border" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>{f.o?.map((o) => <option key={o} value={o}>{o}</option>)}</select>
                    : <input type={f.t} value={(newExp as Record<string,string>)[f.k]} onChange={(e) => setNewExp({...newExp, [f.k]: e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />}
                  </div>
                ))}
                <div className="flex gap-2 pt-4">
                  <button onClick={() => { apiPost("/ai-lab/experiment", { tenant_id: "bein_sports", ...newExp }); setShowNewExp(false); loadData(); }} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Create</button>
                  <button onClick={() => setShowNewExp(false)} className="px-4 py-2 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>)}

      {tab === "models" && (<div>
        <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <LogTable columns={[
            { key: "modelName", label: "Model" }, { key: "version", label: "Version" },
            { key: "isActive", label: "Active", render: (v) => <span style={{ color: v ? "var(--risk-low)" : "var(--text-muted)" }}>{v ? "● Active" : "● Inactive"}</span> },
            { key: "createdAt", label: "Created" },
            { key: "actions", label: "Actions", render: () => (<div className="flex gap-1">
              <button onClick={() => confirm("Switch production model? HIGH risk.")} className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>Switch</button>
              <button onClick={() => confirm("Update model config? HIGH risk.")} className="text-xs px-2 py-0.5 rounded border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Config</button>
            </div>)},
          ]} data={models} />
        </div>
      </div>)}

      {tab === "prompts" && (<div>
        <div className="flex gap-3 mb-4">
          <select value={promptApp} onChange={(e) => setPromptApp(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
            {APPS_LIST.map((a) => <option key={a} value={a}>{a.replace(/_/g, " ")}</option>)}
          </select>
          <select value={promptType} onChange={(e) => setPromptType(e.target.value)} className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
            {["system","analysis","escalation","rca"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button className="px-3 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>+ New Version</button>
          <button className="px-3 py-1.5 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Test</button>
        </div>
        <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Select an app and prompt type to view version history.</p>
        </div>
      </div>)}

      {tab === "evals" && (<div>
        <div className="flex justify-between mb-4">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Model evaluations</p>
          {evalPolling && <span className="text-sm animate-pulse" style={{ color: "var(--brand-primary)" }}>⏳ Evaluation running...</span>}
          <button className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Run Evaluation</button>
        </div>
        <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <LogTable columns={[
            { key: "evalId", label: "ID" }, { key: "app", label: "App" }, { key: "model", label: "Model" },
            { key: "score", label: "Score" }, { key: "runDate", label: "Date" }, { key: "scenariosPassed", label: "Passed" },
          ]} data={[]} />
        </div>
      </div>)}

      {tab === "cost" && (<div>
        {budgetPct > 80 && (
          <div className="mb-4 px-4 py-2 rounded-lg border" style={{ backgroundColor: "var(--risk-medium-bg)", borderColor: "var(--risk-medium)" }}>
            <span className="text-sm font-medium" style={{ color: "var(--risk-medium)" }}>⚠️ Token budget warning ({budgetPct}%) — consider routing more to Haiku</span>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <MetricCard title="Today LLM Cost" value="—" unit="USD" trend="flat" />
          <MetricCard title="7d Cost" value="—" unit="USD" trend="flat" />
          <MetricCard title="Token Budget Used" value={`${budgetPct}`} unit="%" trend="flat" />
          <MetricCard title="Avg Cost/Decision" value="—" unit="USD" trend="flat" />
        </div>
        <div className="rounded-lg border p-3 mb-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>Token Budget</p>
          <div className="w-full h-4 rounded-full" style={{ backgroundColor: "var(--border)" }}>
            <div className="h-4 rounded-full transition-all" style={{ width: `${budgetPct}%`, backgroundColor: budgetColor }} />
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <RechartsWrapper data={[]} xKey="app" yKey="tokens" title="Token Usage by App (stacked)" type="bar" color="var(--brand-primary)" />
          </div>
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <RechartsWrapper data={[]} xKey="date" yKey="cost" title="Daily Cost Trend (30d)" color="var(--brand-accent)" />
          </div>
        </div>
      </div>)}

      <AgentChatPanel appName="AI Lab" />
    </div>
  );
}
