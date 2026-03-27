"use client";
import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import LogTable from "@/components/ui/LogTable";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost } from "@/lib/api";

type Tab = "dashboard" | "experiments" | "models" | "governance";

export default function AILab() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [dash, setDash] = useState<Record<string, unknown> | null>(null);
  const [experiments, setExperiments] = useState<Record<string, unknown>[]>([]);
  const [models, setModels] = useState<Record<string, unknown>[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [modelFilter, setModelFilter] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ name: "", hypothesis: "", variant_a: "", variant_b: "", sample_size: 1000 });

  const loadDash = useCallback(async () => { try { setDash(await apiGet("/ai-lab/dashboard")); } catch {} }, []);
  useEffect(() => { loadDash(); }, [loadDash]);
  useEffect(() => {
    if (tab === "dashboard") { const i = setInterval(loadDash, 60000); return () => clearInterval(i); }
    if (tab === "experiments") { (async () => { try { const r = await apiGet<{items:Record<string,unknown>[]}>(
      `/ai-lab/experiments?limit=20${statusFilter ? `&status=${statusFilter}` : ""}`); setExperiments(r.items ?? []); } catch {} })(); }
    if (tab === "models") { (async () => { try { const r = await apiGet<{items:Record<string,unknown>[]}>(
      `/ai-lab/models${modelFilter ? `?status=${modelFilter}` : ""}`); setModels(r.items ?? []); } catch {} })(); }
  }, [tab, statusFilter, modelFilter, loadDash]);

  const createExp = async () => {
    if (!form.name) return;
    await apiPost("/ai-lab/experiments", form);
    setForm({ name: "", hypothesis: "", variant_a: "", variant_b: "", sample_size: 1000 });
    setShowNew(false); setTab("experiments");
  };

  const d = dash as any;
  const TABS: {key:Tab;label:string}[] = [{key:"dashboard",label:"Dashboard"},{key:"experiments",label:"Experiments"},{key:"models",label:"Models"},{key:"governance",label:"Model Governance"}];

  return (<div>
    <h2 className="text-2xl font-bold mb-6" style={{color:"var(--text-primary)"}}>AI Lab</h2>
    <div className="flex gap-1 mb-6 border-b" style={{borderColor:"var(--border)"}}>
      {TABS.map(t=><button key={t.key} onClick={()=>setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
        style={{borderColor:tab===t.key?"var(--brand-primary)":"transparent",color:tab===t.key?"var(--brand-primary)":"var(--text-secondary)"}}>{t.label}</button>)}
    </div>

    {/* Empty data state */}
    {!d&&tab==="dashboard"&&(
      <div className="flex flex-col items-center justify-center py-20">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
        <p className="mt-3 text-sm font-medium" style={{color:"var(--text-primary)"}}>No data available</p>
        <p className="text-xs mt-1" style={{color:"var(--text-muted)"}}>Connect a data source and run sync to populate this view.</p>
        <a href="/admin-governance" className="mt-3 text-xs px-3 py-1.5 rounded-lg" style={{background:"var(--brand-primary)",color:"#fff"}}>Go to Data Sources →</a>
      </div>
    )}

    {tab==="dashboard"&&d&&(<div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Total Experiments" value={d.total_experiments??0}/>
        <MetricCard title="Running" value={d.running_experiments??0}/>
        <MetricCard title="Completed" value={d.completed_experiments??0}/>
        <MetricCard title="Models in Production" value={d.models_in_production??0}/>
      </div>
      <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <h3 className="text-xs font-semibold mb-3" style={{color:"var(--text-primary)"}}>Recent Experiments</h3>
        {(d.recent_experiments??[]).map((e:any)=>(
          <div key={e.id} className="flex items-center justify-between py-2" style={{borderBottom:"1px solid var(--border)"}}>
            <span className="text-sm" style={{color:"var(--text-primary)"}}>{e.name}</span>
            <div className="flex items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded" style={{
                backgroundColor:e.status==="completed"?"var(--risk-low-bg)":e.status==="running"?"rgba(59,130,246,0.15)":"var(--background)",
                color:e.status==="completed"?"var(--risk-low)":e.status==="running"?"#3b82f6":"var(--text-muted)"
              }}>{e.status}</span>
              <span className="text-xs" style={{color:"var(--text-muted)"}}>{String(e.created_at??"").slice(0,10)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>)}

    {tab==="experiments"&&(<div>
      <div className="flex gap-3 mb-4">
        <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border"
          style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)",color:"var(--text-primary)"}}>
          <option value="">All Status</option><option value="draft">Draft</option><option value="running">Running</option><option value="completed">Completed</option>
        </select>
        <button onClick={()=>setShowNew(!showNew)} className="px-3 py-1.5 rounded text-sm font-medium" style={{backgroundColor:"var(--brand-primary)",color:"#fff"}}>New Experiment</button>
      </div>
      {showNew&&(<div className="rounded-lg border p-4 mb-4 space-y-3" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <input placeholder="Name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{backgroundColor:"var(--background)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
        <input placeholder="Hypothesis" value={form.hypothesis} onChange={e=>setForm({...form,hypothesis:e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{backgroundColor:"var(--background)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
        <div className="grid grid-cols-2 gap-3">
          <input placeholder="Variant A" value={form.variant_a} onChange={e=>setForm({...form,variant_a:e.target.value})} className="text-sm px-3 py-2 rounded border outline-none" style={{backgroundColor:"var(--background)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
          <input placeholder="Variant B" value={form.variant_b} onChange={e=>setForm({...form,variant_b:e.target.value})} className="text-sm px-3 py-2 rounded border outline-none" style={{backgroundColor:"var(--background)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
        </div>
        <button onClick={createExp} className="px-4 py-2 rounded text-sm font-medium" style={{backgroundColor:"var(--brand-primary)",color:"#fff"}}>Create</button>
      </div>)}
      <div className="rounded-lg border" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <LogTable columns={[
          {key:"name",label:"Name"},{key:"hypothesis",label:"Hypothesis",render:v=><span className="text-xs truncate max-w-[200px] inline-block">{String(v??"").slice(0,60)}</span>},
          {key:"status",label:"Status",render:v=><span className="text-xs px-2 py-0.5 rounded" style={{backgroundColor:v==="completed"?"var(--risk-low-bg)":v==="running"?"rgba(59,130,246,0.15)":"var(--background)",color:v==="completed"?"var(--risk-low)":v==="running"?"#3b82f6":"var(--text-muted)"}}>{String(v)}</span>},
          {key:"sample_size",label:"Samples"},{key:"p_value",label:"P-Value",render:v=>v?<span style={{color:Number(v)<0.05?"var(--risk-low)":"var(--text-muted)"}}>{Number(v).toFixed(4)}</span>:<span style={{color:"var(--text-muted)"}}>—</span>},
          {key:"winner",label:"Winner",render:v=>v?<span className="text-xs px-2 py-0.5 rounded" style={{backgroundColor:"var(--risk-low-bg)",color:"var(--risk-low)"}}>{String(v)}</span>:<span style={{color:"var(--text-muted)"}}>—</span>},
        ]} data={experiments as unknown as Record<string,unknown>[]}/>
      </div>
    </div>)}

    {tab==="models"&&(<div>
      <div className="flex gap-3 mb-4">
        <select value={modelFilter} onChange={e=>setModelFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border"
          style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)",color:"var(--text-primary)"}}>
          <option value="">All Status</option><option value="production">Production</option><option value="staging">Staging</option><option value="deprecated">Deprecated</option>
        </select>
      </div>
      <div className="rounded-lg border" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <LogTable columns={[
          {key:"model_name",label:"Model"},{key:"version",label:"Version"},
          {key:"status",label:"Status",render:v=><span className="text-xs px-2 py-0.5 rounded" style={{backgroundColor:v==="production"?"var(--risk-low-bg)":v==="staging"?"rgba(59,130,246,0.15)":"var(--background)",color:v==="production"?"var(--risk-low)":v==="staging"?"#3b82f6":"var(--text-muted)"}}>{String(v)}</span>},
          {key:"accuracy",label:"Accuracy",render:v=>{const a=Number(v);return(<div className="flex items-center gap-2"><div className="w-16 h-1.5 rounded-full" style={{backgroundColor:"var(--border)"}}><div className="h-1.5 rounded-full" style={{width:`${a*100}%`,backgroundColor:a>0.9?"var(--risk-low)":a>0.8?"var(--risk-medium)":"var(--risk-high)"}}/></div><span className="text-xs">{(a*100).toFixed(0)}%</span></div>)}},
          {key:"latency_ms",label:"Latency",render:v=><span>{Number(v).toFixed(0)}ms</span>},
        ]} data={models as unknown as Record<string,unknown>[]}/>
      </div>
    </div>)}

    {tab==="governance"&&(<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <h4 className="text-sm font-semibold mb-2" style={{color:"var(--text-primary)"}}>Token Budget</h4>
        <div className="w-full h-2 rounded-full mb-2" style={{backgroundColor:"var(--border)"}}><div className="h-2 rounded-full" style={{width:"62%",backgroundColor:"var(--risk-low)"}}/></div>
        <p className="text-xs" style={{color:"var(--text-muted)"}}>62% of monthly limit used</p>
      </div>
      <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <h4 className="text-sm font-semibold mb-2" style={{color:"var(--text-primary)"}}>Model Switch Log</h4>
        <p className="text-xs" style={{color:"var(--text-secondary)"}}>Last switch: Haiku→Sonnet for P2 alerts (2 days ago)</p>
      </div>
      <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <h4 className="text-sm font-semibold mb-2" style={{color:"var(--text-primary)"}}>Approval Queue</h4>
        <p className="text-xs" style={{color:"var(--text-muted)"}}>No pending model changes</p>
      </div>
      <p className="text-xs col-span-3" style={{color:"var(--text-muted)"}}>Full governance controls available in Admin & Governance → Usage Stats</p>
    </div>)}

    <AgentChatPanel appName="AI Lab"/>
  </div>);
}
