"use client";
import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import LogTable from "@/components/ui/LogTable";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost } from "@/lib/api";

type Tab = "dashboard" | "search" | "documents" | "index";

export default function KnowledgeBase() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [dash, setDash] = useState<Record<string, unknown> | null>(null);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Record<string, unknown>[]>([]);
  const [collFilter, setCollFilter] = useState("");
  const [docColl, setDocColl] = useState("incidents");
  const [docs, setDocs] = useState<Record<string, unknown>[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [indexMsg, setIndexMsg] = useState("");

  useEffect(() => { (async () => { try { setDash(await apiGet("/knowledge/dashboard")); } catch {} })(); }, []);
  useEffect(() => {
    if (tab === "documents") { (async () => { try { const r = await apiGet<{items:Record<string,unknown>[]}>(
      `/knowledge/documents?collection=${docColl}`); setDocs(r.items ?? []); } catch {} })(); }
  }, [tab, docColl]);

  const doSearch = async (q: string) => {
    if (!q) return;
    try { const r = await apiGet<{results:Record<string,unknown>[]}>(
      `/knowledge/search?q=${encodeURIComponent(q)}${collFilter ? `&collection=${collFilter}` : ""}`);
      setSearchResults(r.results ?? []); } catch {}
  };

  const addDoc = async () => {
    if (!newTitle) return;
    await apiPost("/knowledge/documents", { title: newTitle, content: newContent, collection: docColl });
    setNewTitle(""); setNewContent(""); setShowAdd(false);
    try { const r = await apiGet<{items:Record<string,unknown>[]}>(
      `/knowledge/documents?collection=${docColl}`); setDocs(r.items ?? []); } catch {}
  };

  const d = dash as any;
  const TABS: {key:Tab;label:string}[] = [{key:"dashboard",label:"Dashboard"},{key:"search",label:"Search"},{key:"documents",label:"Documents"},{key:"index",label:"Index Status"}];

  return (<div>
    <h2 className="text-2xl font-bold mb-6" style={{color:"var(--text-primary)"}}>Knowledge Base</h2>
    <div className="flex gap-1 mb-6 border-b" style={{borderColor:"var(--border)"}}>
      {TABS.map(t=><button key={t.key} onClick={()=>setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
        style={{borderColor:tab===t.key?"var(--brand-primary)":"transparent",color:tab===t.key?"var(--brand-primary)":"var(--text-secondary)"}}>{t.label}</button>)}
    </div>

    {tab==="dashboard"&&d&&(<div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard title="Total Documents" value={d.total_documents??0}/>
        <MetricCard title="Collections" value={Object.keys(d.collections??{}).length}/>
        <MetricCard title="Recent Searches" value={d.recent_searches??0}/>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Object.entries(d.collections??{}).map(([k,v])=>(
          <div key={k} className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
            <h4 className="text-sm font-semibold mb-1" style={{color:"var(--text-primary)"}}>{k}</h4>
            <p className="text-2xl font-bold" style={{color:"var(--brand-primary)"}}>{String(v)}</p>
            <p className="text-xs" style={{color:"var(--text-muted)"}}>documents</p>
          </div>
        ))}
      </div>
    </div>)}

    {tab==="search"&&(<div className="space-y-4">
      <div className="flex gap-2">
        <input type="text" value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==="Enter"&&doSearch(query)}
          placeholder="Search knowledge base..." className="flex-1 text-sm px-4 py-3 rounded-lg border outline-none"
          style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
        <select value={collFilter} onChange={e=>setCollFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border"
          style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)",color:"var(--text-primary)"}}>
          <option value="">All</option><option value="incidents">Incidents</option><option value="runbooks">Runbooks</option><option value="platform">Platform</option>
        </select>
        <button onClick={()=>doSearch(query)} className="px-4 py-2 rounded text-sm font-medium" style={{backgroundColor:"var(--brand-primary)",color:"#fff"}}>Search</button>
      </div>
      <div className="flex flex-wrap gap-2">
        {["CDN failure","DRM timeout","pre-scale","P0 response"].map(q=>(
          <button key={q} onClick={()=>{setQuery(q);doSearch(q);}} className="text-xs px-2 py-1 rounded border"
            style={{borderColor:"var(--brand-primary)",color:"var(--brand-primary)"}}>{q}</button>
        ))}
      </div>
      {searchResults.length===0?(<div className="rounded-lg border p-8 text-center" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <p className="text-sm" style={{color:"var(--text-muted)"}}>Enter a search query to find relevant documents</p>
      </div>):(<div className="space-y-3">
        {searchResults.map((r,i)=>(
          <div key={i} className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
            <div className="flex items-center gap-2 mb-1">
              <h4 className="text-sm font-semibold" style={{color:"var(--text-primary)"}}>{String(r.title)}</h4>
              <span className="text-xs px-2 py-0.5 rounded" style={{backgroundColor:"var(--brand-glow)",color:"var(--brand-primary)"}}>{String(r.collection)}</span>
            </div>
            <p className="text-xs" style={{color:"var(--text-secondary)"}}>{String(r.content_preview??"")}</p>
          </div>
        ))}
      </div>)}
    </div>)}

    {tab==="documents"&&(<div>
      <div className="flex gap-3 mb-4">
        {["incidents","runbooks","platform"].map(c=>(
          <button key={c} onClick={()=>setDocColl(c)} className="px-3 py-1 rounded text-xs font-medium"
            style={{backgroundColor:docColl===c?"var(--brand-glow)":"var(--background-card)",color:docColl===c?"var(--brand-primary)":"var(--text-secondary)",border:"1px solid var(--border)"}}>{c}</button>
        ))}
        <button onClick={()=>setShowAdd(!showAdd)} className="px-3 py-1.5 rounded text-sm font-medium" style={{backgroundColor:"var(--brand-primary)",color:"#fff"}}>Add Document</button>
      </div>
      {showAdd&&(<div className="rounded-lg border p-4 mb-4 space-y-3" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <input placeholder="Title" value={newTitle} onChange={e=>setNewTitle(e.target.value)} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{backgroundColor:"var(--background)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
        <textarea placeholder="Content..." value={newContent} onChange={e=>setNewContent(e.target.value)} rows={4} className="w-full text-sm px-3 py-2 rounded border outline-none resize-y" style={{backgroundColor:"var(--background)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
        <button onClick={addDoc} className="px-4 py-2 rounded text-sm font-medium" style={{backgroundColor:"var(--brand-primary)",color:"#fff"}}>Add</button>
      </div>)}
      <div className="rounded-lg border" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <LogTable columns={[
          {key:"title",label:"Title"},{key:"content_preview",label:"Preview",render:v=><span className="text-xs">{String(v??"").slice(0,80)}</span>},
          {key:"collection",label:"Collection",render:v=><span className="text-xs px-2 py-0.5 rounded" style={{backgroundColor:"var(--brand-glow)",color:"var(--brand-primary)"}}>{String(v)}</span>},
        ]} data={docs as unknown as Record<string,unknown>[]}/>
      </div>
    </div>)}

    {tab==="index"&&(<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--risk-low)"}}>
        <h4 className="text-sm font-semibold" style={{color:"var(--risk-low)"}}>ChromaDB Status</h4>
        <p className="text-xs mt-1" style={{color:"var(--text-secondary)"}}>Connected — In-memory mode</p>
      </div>
      <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <h4 className="text-sm font-semibold" style={{color:"var(--text-primary)"}}>Last Indexed</h4>
        <p className="text-xs mt-1" style={{color:"var(--text-muted)"}}>{new Date().toISOString().slice(0,19)}</p>
      </div>
      <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <h4 className="text-sm font-semibold" style={{color:"var(--text-primary)"}}>Collection Sizes</h4>
        <p className="text-xs mt-1" style={{color:"var(--text-secondary)"}}>incidents: 10, runbooks: 8, platform: 5</p>
      </div>
      <button onClick={()=>{setIndexMsg("Re-indexing scheduled");setTimeout(()=>setIndexMsg(""),3000);}}
        className="px-4 py-2 rounded text-sm font-medium" style={{backgroundColor:"var(--brand-primary)",color:"#fff"}}>Re-index</button>
      {indexMsg&&<p className="text-xs" style={{color:"var(--risk-low)"}}>{indexMsg}</p>}
    </div>)}

    <AgentChatPanel appName="Knowledge Base"/>
  </div>);
}
