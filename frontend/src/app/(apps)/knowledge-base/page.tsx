"use client";

import { useState } from "react";
import SeverityBadge from "@/components/ui/SeverityBadge";
import LogTable from "@/components/ui/LogTable";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiPost, apiGet } from "@/lib/api";
import type { SeverityLevel } from "@/types";

type Tab = "search" | "incidents" | "runbooks" | "ingest";

function relevanceColor(score: number): string {
  if (score > 0.8) return "var(--risk-low)";
  if (score > 0.5) return "var(--risk-medium)";
  return "var(--text-muted)";
}

export default function KnowledgeBase() {
  const [tab, setTab] = useState<Tab>("search");
  const [query, setQuery] = useState("");
  const [collection, setCollection] = useState("all");
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<Record<string, unknown> | null>(null);
  const [searching, setSearching] = useState(false);
  const [tagFilter, setTagFilter] = useState("");

  const doSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const r = await apiPost<Record<string, unknown>[]>("/knowledge/search", { query, tenant_id: "bein_sports", collection: collection === "all" ? undefined : collection, top_k: topK });
      setResults(r);
    } catch { setResults([]); }
    setSearching(false);
  };

  const TABS: { key: Tab; label: string }[] = [
    { key: "search", label: "Search" }, { key: "incidents", label: "Incidents" },
    { key: "runbooks", label: "Runbooks" }, { key: "ingest", label: "Ingest" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Knowledge Base</h2>
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>{t.label}</button>
        ))}
      </div>

      {tab === "search" && (<div>
        <div className="flex gap-3 mb-4">
          <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && doSearch()}
            placeholder="Search the knowledge base..." className="flex-1 text-sm px-4 py-3 rounded-lg border outline-none"
            style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
          <button onClick={doSearch} disabled={searching} className="px-6 py-3 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>{searching ? "Searching..." : "Search"}</button>
        </div>
        <div className="flex gap-3 mb-6">
          <div className="flex gap-1">
            {["all","incidents","runbooks","platform"].map((c) => (
              <button key={c} onClick={() => setCollection(c)} className="px-3 py-1 rounded text-xs font-medium capitalize"
                style={{ backgroundColor: collection === c ? "var(--brand-glow)" : "var(--background-card)", color: collection === c ? "var(--brand-primary)" : "var(--text-secondary)", border: "1px solid var(--border)" }}>{c}</button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Top-K:</span>
            {[3,5,10].map((k) => (
              <button key={k} onClick={() => setTopK(k)} className="px-2 py-0.5 rounded text-xs"
                style={{ backgroundColor: topK === k ? "var(--brand-glow)" : "transparent", color: topK === k ? "var(--brand-primary)" : "var(--text-muted)" }}>{k}</button>
            ))}
          </div>
        </div>
        {results.length === 0 && !searching && (
          <div className="rounded-lg border p-12 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <p className="text-lg mb-1" style={{ color: "var(--text-muted)" }}>🔍</p>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>Enter a query to search the knowledge base</p>
          </div>
        )}
        <div className="space-y-3">
          {results.map((r, i) => (
            <div key={i} onClick={() => setSelectedDoc(r)} className="rounded-lg border p-4 cursor-pointer transition-colors"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--brand-primary)")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{String(r.title || "Untitled")}</h4>
                <div className="flex gap-2">
                  <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>{String(r.collection)}</span>
                  <span className="text-xs px-2 py-0.5 rounded font-mono" style={{ color: relevanceColor(r.relevanceScore as number) }}>{((r.relevanceScore as number) ?? 0).toFixed(2)}</span>
                </div>
              </div>
              <p className="text-xs line-clamp-2" style={{ color: "var(--text-secondary)" }}>{String(r.content || "").slice(0, 200)}</p>
            </div>
          ))}
        </div>
        {selectedDoc && (
          <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => setSelectedDoc(null)}>
            <div className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between mb-4"><h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>{String(selectedDoc.title)}</h3><button onClick={() => setSelectedDoc(null)} style={{ color: "var(--text-muted)" }}>✕</button></div>
              <div className="prose prose-sm prose-invert max-w-none text-sm" style={{ color: "var(--text-secondary)" }}>
                <pre className="whitespace-pre-wrap p-3 rounded" style={{ backgroundColor: "var(--background)" }}>{String(selectedDoc.content)}</pre>
              </div>
            </div>
          </div>
        )}
      </div>)}

      {tab === "incidents" && (<div>
        <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <LogTable columns={[
            { key: "incidentId", label: "Incident ID" }, { key: "title", label: "Title" },
            { key: "severity", label: "Severity", render: (v) => <SeverityBadge severity={v as SeverityLevel} /> },
            { key: "indexedAt", label: "Indexed At" },
            { key: "rcaAvailable", label: "RCA", render: (v) => v ? <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--risk-low-bg)", color: "var(--risk-low)" }}>✓ RCA</span> : <span className="text-xs" style={{ color: "var(--text-muted)" }}>—</span> },
          ]} data={[]} />
        </div>
      </div>)}

      {tab === "runbooks" && (<div>
        <div className="flex gap-2 mb-4 flex-wrap">
          {["all","cdn","drm","deployment","scaling"].map((t) => (
            <button key={t} onClick={() => setTagFilter(t === "all" ? "" : t)} className="px-3 py-1 rounded text-xs capitalize"
              style={{ backgroundColor: (tagFilter === t || (t === "all" && !tagFilter)) ? "var(--brand-glow)" : "var(--background-card)", color: (tagFilter === t || (t === "all" && !tagFilter)) ? "var(--brand-primary)" : "var(--text-secondary)", border: "1px solid var(--border)" }}>{t}</button>
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-lg border p-4 col-span-2 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>No runbooks yet. Upload via Ingest tab.</p>
          </div>
        </div>
      </div>)}

      {tab === "ingest" && (<div>
        <div className="rounded-lg border-2 border-dashed p-8 text-center mb-6" style={{ borderColor: "var(--border)" }}>
          <p className="text-lg mb-1" style={{ color: "var(--text-muted)" }}>📄</p>
          <p className="text-sm mb-2" style={{ color: "var(--text-secondary)" }}>Drag & drop files here, or click to browse</p>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Supported: PDF, MD, TXT</p>
          <div className="flex justify-center gap-3 mt-4">
            <select className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="incidents">Incidents</option><option value="runbooks">Runbooks</option><option value="platform">Platform</option>
            </select>
            <button className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Upload</button>
          </div>
        </div>
        <h4 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Recent Ingestions</h4>
        <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <LogTable columns={[
            { key: "filename", label: "File" }, { key: "collection", label: "Collection" },
            { key: "chunks", label: "Chunks" }, { key: "status", label: "Status" }, { key: "ingestedAt", label: "Ingested" },
            { key: "actions", label: "", render: () => <button onClick={() => confirm("Delete document? HIGH risk action.")} className="text-xs px-2 py-0.5 rounded" style={{ color: "var(--risk-high)" }}>Delete</button> },
          ]} data={[]} />
        </div>
      </div>)}

      <AgentChatPanel appName="Knowledge Base" />
    </div>
  );
}
