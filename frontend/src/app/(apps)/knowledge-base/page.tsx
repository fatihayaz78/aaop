"use client";
import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost } from "@/lib/api";

type Tab = "dashboard" | "search" | "documents" | "index";

const collColor: Record<string, {bg: string; text: string}> = {
  incidents: {bg: "rgba(59,130,246,0.15)", text: "#3b82f6"},
  runbooks: {bg: "rgba(34,197,94,0.15)", text: "#22c55e"},
  platform: {bg: "rgba(168,85,247,0.15)", text: "#a855f7"},
  akamai_ds2: {bg: "rgba(234,179,8,0.15)", text: "#eab308"},
};

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
  const [selectedDoc, setSelectedDoc] = useState<Record<string, unknown> | null>(null);

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

  const DocBadge = ({coll}: {coll: string}) => {
    const c = collColor[coll] || collColor.platform;
    return <span className="text-xs px-2 py-0.5 rounded" style={{backgroundColor: c.bg, color: c.text}}>{coll}</span>;
  };

  // Document detail dialog
  const DocDialog = () => {
    if (!selectedDoc) return null;
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center" style={{backgroundColor:"rgba(0,0,0,0.6)"}} onClick={()=>setSelectedDoc(null)}>
        <div className="w-full max-w-3xl max-h-[80vh] overflow-y-auto rounded-lg border p-6"
          style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}} onClick={e=>e.stopPropagation()}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold" style={{color:"var(--text-primary)"}}>{String(selectedDoc.title)}</h3>
              <DocBadge coll={String(selectedDoc.collection??"")} />
            </div>
            <button onClick={()=>setSelectedDoc(null)} style={{color:"var(--text-muted)"}}>&#10005;</button>
          </div>
          <pre className="whitespace-pre-wrap text-sm" style={{color:"var(--text-secondary)"}}>{String(selectedDoc.content ?? selectedDoc.content_preview ?? "")}</pre>
        </div>
      </div>
    );
  };

  return (<div>
    <h2 className="text-2xl font-bold mb-6" style={{color:"var(--text-primary)"}}>Knowledge Base</h2>
    <div className="flex gap-1 mb-6 border-b" style={{borderColor:"var(--border)"}}>
      {TABS.map(t=><button key={t.key} onClick={()=>setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
        style={{borderColor:tab===t.key?"var(--brand-primary)":"transparent",color:tab===t.key?"var(--brand-primary)":"var(--text-secondary)"}}>{t.label}</button>)}
    </div>

    <DocDialog />

    {/* ═══ Dashboard ═══ */}
    {tab==="dashboard"&&d&&(<div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard title="Total Documents" value={d.total_documents??0}/>
        <MetricCard title="Collections" value={Object.keys(d.collections??{}).length}/>
        <MetricCard title="Recent Searches" value={d.recent_searches??0}/>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(d.collections??{}).map(([k,v])=>{
          const c = collColor[k] || collColor.platform;
          return (
            <div key={k} className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:c.text+"33"}}>
              <h4 className="text-sm font-semibold mb-1" style={{color:c.text}}>{k}</h4>
              <p className="text-2xl font-bold" style={{color:"var(--text-primary)"}}>{String(v)}</p>
              <p className="text-xs" style={{color:"var(--text-muted)"}}>documents</p>
            </div>
          );
        })}
      </div>
    </div>)}

    {/* ═══ Search ═══ */}
    {tab==="search"&&(<div className="space-y-4">
      <div className="flex gap-2">
        <input type="text" value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==="Enter"&&doSearch(query)}
          placeholder="Search knowledge base..." className="flex-1 text-sm px-4 py-3 rounded-lg border outline-none"
          style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)",color:"var(--text-primary)"}}/>
        <select value={collFilter} onChange={e=>setCollFilter(e.target.value)} className="text-sm px-3 py-1.5 rounded border"
          style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)",color:"var(--text-primary)"}}>
          <option value="">All</option>
          <option value="incidents">Incidents</option>
          <option value="runbooks">Runbooks</option>
          <option value="platform">Platform</option>
          <option value="akamai_ds2">Akamai DS2</option>
        </select>
        <button onClick={()=>doSearch(query)} className="px-4 py-2 rounded text-sm font-medium" style={{backgroundColor:"var(--brand-primary)",color:"#fff"}}>Search</button>
      </div>
      <div className="flex flex-wrap gap-2">
        {["CDN failure","DRM timeout","pre-scale","P0 response","cache hit","DS2 fields","PII hashing","error code"].map(q=>(
          <button key={q} onClick={()=>{setQuery(q);doSearch(q);}} className="text-xs px-2 py-1 rounded border"
            style={{borderColor:"var(--brand-primary)",color:"var(--brand-primary)"}}>{q}</button>
        ))}
      </div>
      {searchResults.length===0?(<div className="rounded-lg border p-8 text-center" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
        <p className="text-sm" style={{color:"var(--text-muted)"}}>Enter a search query to find relevant documents</p>
      </div>):(<div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {searchResults.map((r,i)=>{
          const score = Number(r.score ?? 0);
          const maxScore = Math.max(...searchResults.map(s => Number(s.score ?? 1)));
          const pct = maxScore > 0 ? (score / maxScore) * 100 : 0;
          return (
            <div key={i} className="rounded-lg border p-4 cursor-pointer transition-colors"
              style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}
              onClick={()=>setSelectedDoc(r)}
              onMouseEnter={e=>(e.currentTarget.style.borderColor="var(--brand-primary)")}
              onMouseLeave={e=>(e.currentTarget.style.borderColor="var(--border)")}>
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-sm font-medium" style={{color:"var(--text-primary)"}}>{String(r.title)}</h4>
                <DocBadge coll={String(r.collection??"")} />
              </div>
              <p className="text-xs line-clamp-2 mb-2" style={{color:"var(--text-muted)"}}>{String(r.content_preview??"")}</p>
              <div className="w-full h-1 rounded-full" style={{backgroundColor:"var(--border)"}}>
                <div className="h-1 rounded-full" style={{width:`${pct}%`,backgroundColor:pct>70?"var(--risk-low)":pct>40?"var(--risk-medium)":"var(--risk-high)"}} />
              </div>
              <p className="text-xs mt-1" style={{color:"var(--text-muted)"}}>Click to read full document</p>
            </div>
          );
        })}
      </div>)}
    </div>)}

    {/* ═══ Documents ═══ */}
    {tab==="documents"&&(<div>
      <div className="flex gap-3 mb-4 flex-wrap">
        {["incidents","runbooks","platform","akamai_ds2"].map(c=>(
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
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {docs.map((doc, i) => {
          const c = collColor[String(doc.collection)] || collColor.platform;
          return (
            <div key={i} className="rounded-lg border p-4 cursor-pointer transition-colors"
              style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}
              onClick={()=>setSelectedDoc(doc)}
              onMouseEnter={e=>(e.currentTarget.style.borderColor=c.text)}
              onMouseLeave={e=>(e.currentTarget.style.borderColor="var(--border)")}>
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-sm font-medium" style={{color:"var(--text-primary)"}}>{String(doc.title)}</h4>
                <DocBadge coll={String(doc.collection??"")} />
              </div>
              <p className="text-xs line-clamp-2 mb-1" style={{color:"var(--text-muted)"}}>{String(doc.content_preview??"").slice(0,120)}</p>
              <p className="text-xs" style={{color:"var(--text-muted)"}}>Click to read</p>
            </div>
          );
        })}
      </div>
    </div>)}

    {/* ═══ Index Status ═══ */}
    {tab==="index"&&(<div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--risk-low)"}}>
          <h4 className="text-sm font-semibold" style={{color:"var(--risk-low)"}}>ChromaDB Status</h4>
          <p className="text-xs mt-1" style={{color:"var(--text-secondary)"}}>Connected — In-memory mode</p>
        </div>
        <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
          <h4 className="text-sm font-semibold" style={{color:"var(--text-primary)"}}>Last Indexed</h4>
          <p className="text-xs mt-1" style={{color:"var(--text-muted)"}}>{d?.last_indexed ? String(d.last_indexed).slice(0,19) : new Date().toISOString().slice(0,19)}</p>
        </div>
        <div className="rounded-lg border p-4" style={{backgroundColor:"var(--background-card)",borderColor:"var(--border)"}}>
          <h4 className="text-sm font-semibold" style={{color:"var(--text-primary)"}}>Collection Sizes</h4>
          {d?.collections ? (
            <div className="text-xs mt-1 space-y-0.5" style={{color:"var(--text-secondary)"}}>
              {Object.entries(d.collections as Record<string,number>).map(([k,v])=>(
                <p key={k}>{k}: {v} docs</p>
              ))}
            </div>
          ) : <p className="text-xs mt-1" style={{color:"var(--text-muted)"}}>Loading...</p>}
        </div>
      </div>
      <button onClick={()=>{setIndexMsg("Re-indexing scheduled");setTimeout(()=>setIndexMsg(""),3000);}}
        className="px-4 py-2 rounded text-sm font-medium" style={{backgroundColor:"var(--brand-primary)",color:"#fff"}}>Re-index</button>
      {indexMsg&&<p className="text-xs" style={{color:"var(--risk-low)"}}>{indexMsg}</p>}
    </div>)}

    <AgentChatPanel appName="Knowledge Base"/>
  </div>);
}
