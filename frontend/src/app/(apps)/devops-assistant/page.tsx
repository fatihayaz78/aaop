"use client";
import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost } from "@/lib/api";

type Tab = "dashboard" | "chat" | "runbooks";

export default function DevOpsAssistant() {
  const [tab, setTab] = useState<Tab>("chat");
  const [dash, setDash] = useState<Record<string, unknown> | null>(null);
  const [messages, setMessages] = useState<{role:string;content:string;sources?:string[];blocked?:boolean}[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [runbooks, setRunbooks] = useState<Record<string, unknown>[]>([]);
  const [rbQuery, setRbQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => { (async () => { try { setDash(await apiGet("/devops/dashboard")); } catch {} })(); }, []);
  useEffect(() => {
    if (tab === "runbooks") { (async () => { try {
      const url = rbQuery ? `/devops/runbooks/search?q=${encodeURIComponent(rbQuery)}` : "/devops/runbooks";
      const r = await apiGet<{items?:Record<string,unknown>[];results?:Record<string,unknown>[]}>(url);
      setRunbooks(r.items ?? r.results ?? []);
    } catch {} })(); }
  }, [tab, rbQuery]);

  const send = async (msg: string) => {
    if (!msg.trim()) return;
    setMessages(p => [...p, { role: "user", content: msg }]);
    setInput(""); setLoading(true);
    try {
      const r = await apiPost<{response:string;sources?:string[];blocked?:boolean;reason?:string}>("/devops/chat", { message: msg });
      if (r.blocked) {
        setMessages(p => [...p, { role: "assistant", content: r.reason || "Command blocked", blocked: true }]);
      } else {
        setMessages(p => [...p, { role: "assistant", content: r.response, sources: r.sources }]);
      }
    } catch { setMessages(p => [...p, { role: "assistant", content: "Error connecting." }]); }
    setLoading(false);
  };

  const d = dash as any;
  const TABS: {key:Tab;label:string}[] = [{key:"dashboard",label:"Dashboard"},{key:"chat",label:"Chat"},{key:"runbooks",label:"Runbooks"}];

  return (<div>
    <h2 className="text-2xl font-bold mb-6" style={{color:"var(--text-primary)"}}>DevOps Assistant</h2>
    <div className="flex gap-1 mb-6 border-b" style={{borderColor:"var(--border)"}}>
      {TABS.map(t=><button key={t.key} onClick={()=>setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
        style={{borderColor:tab===t.key?"var(--brand-primary)":"transparent",color:tab===t.key?"var(--brand-primary)":"var(--text-secondary)"}}>{t.label}</button>)}
    </div>

    {tab==="dashboard"&&d&&(<div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard title="Runbooks Available" value={d.runbooks_available??0}/>
        <MetricCard title="Queries Today" value={d.recent_queries_24h??0}/>
        <MetricCard title="Blocked Commands" value={d.dangerous_commands_blocked??0}/>
      </div>
      <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <h3 className="text-xs font-semibold mb-2" style={{color:"var(--text-primary)"}}>Top Topics</h3>
        <div className="flex flex-wrap gap-2">
          {(d.top_topics??[]).map((t:string)=>(
            <span key={t} className="text-xs px-2 py-1 rounded" style={{backgroundColor:"var(--brand-glow)",color:"var(--brand-primary)"}}>{t}</span>
          ))}
        </div>
      </div>
      <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <h3 className="text-xs font-semibold mb-3" style={{color:"var(--text-primary)"}}>Quick Actions</h3>
        <div className="grid grid-cols-2 gap-2">
          {["How to purge CDN cache?","P0 incident checklist","DRM fallback steps","Scale up encoder"].map(q=>(
            <button key={q} onClick={()=>{setTab("chat");setTimeout(()=>send(q),100);}} className="text-xs px-3 py-2 rounded border text-left"
              style={{borderColor:"var(--border)",color:"var(--text-secondary)",backgroundColor:"var(--background)"}}>{q}</button>
          ))}
        </div>
      </div>
    </div>)}

    {tab==="chat"&&(<div>
      <p className="text-xs mb-3" style={{color:"var(--text-muted)"}}>DevOps Assistant — OTT Platform Expert</p>
      <div className="rounded-lg border p-4 mb-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)",minHeight:"400px"}}>
        <div className="space-y-3 mb-4" style={{maxHeight:"350px",overflowY:"auto"}}>
          {messages.length===0&&(
            <div className="space-y-2">
              <p className="text-sm text-center" style={{color:"var(--text-muted)"}}>Ask me anything about your OTT platform</p>
              <div className="flex flex-wrap gap-2 justify-center">
                {["How do I purge Akamai cache for a specific CP code?","What are the steps for P0 incident response?",
                  "How to activate DRM fallback?","CDN token auth is failing — what to check?"].map(q=>(
                  <button key={q} onClick={()=>send(q)} className="text-xs px-2 py-1 rounded border"
                    style={{borderColor:"var(--brand-primary)",color:"var(--brand-primary)"}}>{q}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m,i)=>(
            <div key={i} className={`flex ${m.role==="user"?"justify-end":"justify-start"}`}>
              <div className="max-w-[80%] rounded-lg px-3 py-2 text-sm" style={{
                backgroundColor:m.blocked?"var(--risk-high-bg)":m.role==="user"?"var(--brand-primary)":"var(--background)",
                color:m.blocked?"var(--risk-high)":m.role==="user"?"#fff":"var(--text-secondary)",
                border:m.blocked?"1px solid var(--risk-high)":"none"}}>
                {m.blocked&&<span className="font-bold">&#9888; </span>}
                <pre className="whitespace-pre-wrap font-sans text-sm">{m.content}</pre>
                {m.sources&&m.sources.length>0&&(
                  <div className="flex flex-wrap gap-1 mt-2 pt-2" style={{borderTop:"1px solid var(--border)"}}>
                    {m.sources.map((s,j)=><span key={j} className="text-xs px-1.5 py-0.5 rounded" style={{backgroundColor:"var(--background)",color:"var(--text-muted)"}}>{s}</span>)}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading&&(<div className="flex justify-start"><div className="rounded-lg px-3 py-2 text-sm flex items-center gap-2" style={{backgroundColor:"var(--background)",color:"var(--text-muted)"}}>
            <div className="w-3 h-3 border-2 rounded-full animate-spin" style={{borderColor:"var(--border)",borderTopColor:"var(--brand-primary)"}}/>Thinking...</div></div>)}
        </div>
      </div>
      <div className="flex gap-2">
        <input type="text" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&!loading&&send(input)}
          placeholder="Ask about CDN, DRM, scaling, incidents..." className="flex-1 text-sm px-3 py-2 rounded border outline-none"
          style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
        <button onClick={()=>send(input)} disabled={loading} className="px-4 py-2 rounded text-sm font-medium disabled:opacity-50"
          style={{backgroundColor:"var(--brand-primary)",color:"#fff"}}>Send</button>
      </div>
    </div>)}

    {tab==="runbooks"&&(<div>
      <div className="flex gap-2 mb-4">
        <input type="text" value={rbQuery} onChange={e=>setRbQuery(e.target.value)} placeholder="Search runbooks..."
          className="flex-1 text-sm px-3 py-2 rounded border outline-none" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
      </div>
      <div className="space-y-3">
        {runbooks.map((r,i)=>(
          <div key={i} className="rounded-lg border p-4 cursor-pointer" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}
            onClick={()=>setExpanded(expanded===String(r.id)?null:String(r.id))}>
            <h4 className="text-sm font-semibold" style={{color:"var(--text-primary)"}}>{String(r.title)}</h4>
            <p className="text-xs mt-1" style={{color:"var(--text-secondary)"}}>{expanded===String(r.id)?String(r.content??r.content_preview??""):String(r.content_preview??"").slice(0,100)}</p>
          </div>
        ))}
        {runbooks.length===0&&<p className="text-sm text-center" style={{color:"var(--text-muted)"}}>No runbooks found</p>}
      </div>
    </div>)}
  </div>);
}
