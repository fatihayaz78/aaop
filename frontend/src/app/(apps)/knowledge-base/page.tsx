"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";

// ── Types ──

type FaqTab = "general" | "modules";
type GeneralSubTab = "overview" | "architecture" | "api" | "schemas";
type ModuleId =
  | "ops_center" | "log_analyzer" | "alert_center" | "viewer_experience"
  | "live_intelligence" | "growth_retention" | "capacity_cost"
  | "admin_governance" | "ai_lab" | "devops_assistant" | "knowledge_base";

// ── Constants ──

const GENERAL_FILES: Record<GeneralSubTab, string> = {
  overview: "/kb/index.html",
  architecture: "/kb/architecture.html",
  api: "/kb/api_reference.html",
  schemas: "/kb/log_schemas.html",
};

const GENERAL_LABELS: Record<GeneralSubTab, string> = {
  overview: "Platform Overview",
  architecture: "Architecture",
  api: "API Reference",
  schemas: "Log Schemas",
};

const MODULE_FILES: Record<ModuleId, string> = {
  ops_center: "/kb/ops_center.html",
  log_analyzer: "/kb/log_analyzer.html",
  alert_center: "/kb/alert_center.html",
  viewer_experience: "/kb/viewer_experience.html",
  live_intelligence: "/kb/live_intelligence.html",
  growth_retention: "/kb/growth_retention.html",
  capacity_cost: "/kb/capacity_cost.html",
  admin_governance: "/kb/admin_governance.html",
  ai_lab: "/kb/ai_lab.html",
  devops_assistant: "/kb/devops_assistant.html",
  knowledge_base: "/kb/knowledge_base.html",
};

const MODULE_LABELS: Record<ModuleId, string> = {
  ops_center: "Ops Center",
  log_analyzer: "Log Analyzer",
  alert_center: "Alert Center",
  viewer_experience: "Viewer Experience",
  live_intelligence: "Live Intelligence",
  growth_retention: "Growth & Retention",
  capacity_cost: "Capacity & Cost",
  admin_governance: "Admin & Governance",
  ai_lab: "AI Lab",
  devops_assistant: "DevOps Assistant",
  knowledge_base: "Knowledge Base",
};

const MODULE_SECTIONS: Record<ModuleId, { label: string; tabId: string }[]> = {
  ops_center: [
    { label: "Overview", tabId: "overview" }, { label: "Agents", tabId: "agents" },
    { label: "Tools", tabId: "tools" }, { label: "API", tabId: "api" },
    { label: "Cross-App", tabId: "crossapp" }, { label: "Data & Storage", tabId: "data" },
    { label: "Business Rules", tabId: "rules" },
  ],
  log_analyzer: [
    { label: "Overview", tabId: "overview" }, { label: "Sub-Modules", tabId: "submodules" },
    { label: "Akamai DS2", tabId: "akamai" }, { label: "Agent & Tools", tabId: "agent" },
    { label: "API", tabId: "api" }, { label: "Cross-App", tabId: "crossapp" },
    { label: "Data & Storage", tabId: "data" },
  ],
  alert_center: [
    { label: "Overview", tabId: "overview" }, { label: "Agent", tabId: "agent" },
    { label: "Routing Logic", tabId: "routing" }, { label: "Tools", tabId: "tools" },
    { label: "API", tabId: "api" }, { label: "Cross-App", tabId: "crossapp" },
    { label: "Data & Storage", tabId: "data" },
  ],
  viewer_experience: [
    { label: "Overview", tabId: "overview" }, { label: "QoE Agent", tabId: "qoe" },
    { label: "Complaint Agent", tabId: "complaint" }, { label: "Tools", tabId: "tools" },
    { label: "API", tabId: "api" }, { label: "Cross-App", tabId: "crossapp" },
    { label: "Data & Storage", tabId: "data" },
  ],
  live_intelligence: [
    { label: "Overview", tabId: "overview" }, { label: "Live Event Agent", tabId: "liveevent" },
    { label: "External Data Agent", tabId: "external" }, { label: "Tools", tabId: "tools" },
    { label: "API", tabId: "api" }, { label: "Cross-App", tabId: "crossapp" },
    { label: "Data & Storage", tabId: "data" },
  ],
  growth_retention: [
    { label: "Overview", tabId: "overview" }, { label: "Growth Agent", tabId: "growth" },
    { label: "Data Analyst Agent", tabId: "analyst" }, { label: "Tools", tabId: "tools" },
    { label: "API", tabId: "api" }, { label: "Cross-App", tabId: "crossapp" },
    { label: "Data & Storage", tabId: "data" },
  ],
  capacity_cost: [
    { label: "Overview", tabId: "overview" }, { label: "Capacity Agent", tabId: "capacity" },
    { label: "Automation Agent", tabId: "automation" }, { label: "Tools", tabId: "tools" },
    { label: "API", tabId: "api" }, { label: "Cross-App", tabId: "crossapp" },
    { label: "Data & Storage", tabId: "data" },
  ],
  admin_governance: [
    { label: "Overview", tabId: "overview" }, { label: "Tenant Agent", tabId: "tenant" },
    { label: "Compliance Agent", tabId: "compliance" }, { label: "Tools", tabId: "tools" },
    { label: "API", tabId: "api" }, { label: "Data & Storage", tabId: "data" },
  ],
  ai_lab: [
    { label: "Overview", tabId: "tab-overview" }, { label: "Experiment Agent", tabId: "tab-experiment" },
    { label: "ML Gov Agent", tabId: "tab-mlgov" }, { label: "Tools", tabId: "tab-tools" },
    { label: "API", tabId: "tab-api" }, { label: "Data & Storage", tabId: "tab-data" },
  ],
  devops_assistant: [
    { label: "Overview", tabId: "tab-overview" }, { label: "Agent", tabId: "tab-agent" },
    { label: "Tools", tabId: "tab-tools" }, { label: "API", tabId: "tab-api" },
    { label: "Data & Storage", tabId: "tab-data" },
  ],
  knowledge_base: [
    { label: "Overview", tabId: "search" }, { label: "AI Agent", tabId: "search" },
    { label: "Collections", tabId: "search" }, { label: "API", tabId: "search" },
    { label: "Cross-App", tabId: "search" }, { label: "Redis Keys", tabId: "search" },
    { label: "Business Rules", tabId: "search" },
  ],
};

const ALL_MODULES: ModuleId[] = [
  "ops_center", "log_analyzer", "alert_center", "viewer_experience",
  "live_intelligence", "growth_retention", "capacity_cost",
  "admin_governance", "ai_lab", "devops_assistant", "knowledge_base",
];

const collColor: Record<string, { bg: string; text: string }> = {
  incidents: { bg: "rgba(59,130,246,0.15)", text: "#3b82f6" },
  runbooks: { bg: "rgba(34,197,94,0.15)", text: "#22c55e" },
  platform: { bg: "rgba(168,85,247,0.15)", text: "#a855f7" },
  akamai_ds2: { bg: "rgba(234,179,8,0.15)", text: "#eab308" },
};

// ── Main Component ──

export default function KnowledgeBase() {
  const searchParams = useSearchParams();
  const viewParam = searchParams?.get("view") || "faq";
  const view = viewParam === "documents" ? "documents" : "faq";

  const [faqTab, setFaqTab] = useState<FaqTab>("general");
  const [generalSubTab, setGeneralSubTab] = useState<GeneralSubTab>("overview");
  const [selectedModule, setSelectedModule] = useState<ModuleId | null>(null);
  const [moduleSection, setModuleSection] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Breadcrumb
  const breadcrumb: string[] = [];
  if (view === "faq") {
    breadcrumb.push("FAQ");
    if (faqTab === "general") {
      breadcrumb.push("General");
      breadcrumb.push(GENERAL_LABELS[generalSubTab]);
    } else {
      breadcrumb.push("Modules");
      if (selectedModule) {
        breadcrumb.push(MODULE_LABELS[selectedModule]);
        breadcrumb.push(MODULE_SECTIONS[selectedModule][moduleSection]?.label || "");
      }
    }
  } else {
    breadcrumb.push("Documents");
  }

  const handleSectionClick = (idx: number) => {
    setModuleSection(idx);
    if (!selectedModule) return;
    const section = MODULE_SECTIONS[selectedModule][idx];
    if (!section) return;
    try {
      iframeRef.current?.contentWindow?.postMessage({ type: "showTab", tabId: section.tabId }, "*");
    } catch { /* cross-origin */ }
  };

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 80px)" }}>
      {/* ── Sticky Search ── */}
      <div className="flex-shrink-0 px-6 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search in Knowledge Base..."
          className="w-full text-sm px-4 py-2.5 rounded-lg border outline-none"
          style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}
        />
      </div>

      {/* ── Breadcrumb ── */}
      <div className="flex-shrink-0 px-6 py-2" style={{ borderBottom: "1px solid var(--border)" }}>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          {breadcrumb.map((b, i) => (
            <span key={i}>
              {i > 0 && <span className="mx-1">&gt;</span>}
              <span style={{ color: i === breadcrumb.length - 1 ? "var(--text-primary)" : "var(--text-muted)" }}>{b}</span>
            </span>
          ))}
        </p>
      </div>

      {/* ═══ FAQ View ═══ */}
      {view === "faq" && (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* FAQ Tab Bar */}
          <div className="flex-shrink-0 flex gap-1 px-6 pt-3" style={{ borderBottom: "1px solid var(--border)" }}>
            {(["general", "modules"] as FaqTab[]).map((t) => (
              <button key={t} onClick={() => { setFaqTab(t); setSelectedModule(null); }}
                className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors capitalize"
                style={{ borderColor: faqTab === t ? "var(--brand-primary)" : "transparent", color: faqTab === t ? "var(--brand-primary)" : "var(--text-secondary)" }}>
                {t}
              </button>
            ))}
          </div>

          {/* General sub-tabs + iframe */}
          {faqTab === "general" && (
            <>
              <div className="flex-shrink-0 flex gap-1 px-6 pt-2" style={{ borderBottom: "1px solid var(--border)" }}>
                {(Object.keys(GENERAL_FILES) as GeneralSubTab[]).map((st) => (
                  <button key={st} onClick={() => setGeneralSubTab(st)}
                    className="px-3 pb-2 text-xs font-medium border-b-2 transition-colors"
                    style={{ borderColor: generalSubTab === st ? "var(--brand-primary)" : "transparent", color: generalSubTab === st ? "var(--brand-primary)" : "var(--text-muted)" }}>
                    {GENERAL_LABELS[st]}
                  </button>
                ))}
              </div>
              <div className="flex-1">
                <iframe ref={iframeRef} src={GENERAL_FILES[generalSubTab]} style={{ width: "100%", height: "100%", border: "none" }} title={GENERAL_LABELS[generalSubTab]} />
              </div>
            </>
          )}

          {/* Modules: card grid */}
          {faqTab === "modules" && !selectedModule && (
            <div className="flex-1 overflow-y-auto p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {ALL_MODULES.map((m) => {
                  const isP0 = ["ops_center", "log_analyzer", "alert_center"].includes(m);
                  const isP2 = ["ai_lab", "devops_assistant", "knowledge_base"].includes(m);
                  const bc = isP0 ? "var(--status-error)" : isP2 ? "var(--brand-primary)" : "var(--status-warning)";
                  const pr = isP0 ? "P0" : isP2 ? "P2" : "P1";
                  return (
                    <div key={m} onClick={() => { setSelectedModule(m); setModuleSection(0); }}
                      className="rounded-lg border p-4 cursor-pointer transition-all"
                      style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", borderTop: `3px solid ${bc}` }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = bc; }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border)"; (e.currentTarget as HTMLElement).style.borderTop = `3px solid ${bc}`; }}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{MODULE_LABELS[m]}</span>
                        <span className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ background: isP0 ? "var(--risk-high-bg)" : isP2 ? "var(--brand-glow)" : "var(--risk-medium-bg)", color: bc }}>{pr}</span>
                      </div>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>{MODULE_SECTIONS[m].length} sections</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Module detail: section tabs + iframe */}
          {faqTab === "modules" && selectedModule && (
            <>
              <div className="flex-shrink-0 px-6 pt-2">
                <button onClick={() => { setSelectedModule(null); setModuleSection(0); }} className="text-xs" style={{ color: "var(--brand-primary)" }}>&larr; Back to Modules</button>
              </div>
              <div className="flex-shrink-0 flex gap-1 px-6 pb-0 overflow-x-auto" style={{ borderBottom: "1px solid var(--border)" }}>
                {MODULE_SECTIONS[selectedModule].map((sec, idx) => (
                  <button key={sec.tabId + idx} onClick={() => handleSectionClick(idx)}
                    className="px-3 pb-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap"
                    style={{ borderColor: moduleSection === idx ? "var(--brand-primary)" : "transparent", color: moduleSection === idx ? "var(--brand-primary)" : "var(--text-muted)" }}>
                    {sec.label}
                  </button>
                ))}
              </div>
              <div className="flex-1">
                <iframe ref={iframeRef} src={MODULE_FILES[selectedModule]} style={{ width: "100%", height: "100%", border: "none" }} title={MODULE_LABELS[selectedModule]} />
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══ Documents View ═══ */}
      {view === "documents" && <DocumentsView searchQuery={searchQuery} />}
    </div>
  );
}

// ── Documents View ──

function DocumentsView({ searchQuery }: { searchQuery: string }) {
  const [docs, setDocs] = useState<Record<string, unknown>[]>([]);
  const [filter, setFilter] = useState("all");
  const [showAdd, setShowAdd] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<Record<string, unknown> | null>(null);

  const loadDocs = useCallback(async () => {
    try {
      const { apiGet } = await import("@/lib/api");
      const coll = filter === "all" ? "" : filter;
      const r = await apiGet<{ items: Record<string, unknown>[] }>(`/knowledge/documents${coll ? `?collection=${coll}` : ""}`);
      setDocs(r.items ?? []);
    } catch { setDocs([]); }
  }, [filter]);

  useEffect(() => { loadDocs(); }, [loadDocs]);

  const addDoc = async () => {
    if (!newTitle) return;
    try {
      const { apiPost } = await import("@/lib/api");
      await apiPost("/knowledge/documents", { title: newTitle, content: newContent, collection: filter === "all" ? "platform" : filter });
      setNewTitle(""); setNewContent(""); setShowAdd(false); loadDocs();
    } catch { /* */ }
  };

  const filtered = searchQuery
    ? docs.filter((d) => `${String(d.title)} ${String(d.content_preview ?? "")}`.toLowerCase().includes(searchQuery.toLowerCase()))
    : docs;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="flex gap-1 mb-4" style={{ borderBottom: "1px solid var(--border)" }}>
        {["all", "incidents", "runbooks", "platform", "akamai_ds2"].map((c) => (
          <button key={c} onClick={() => setFilter(c)}
            className="px-3 pb-2 text-xs font-medium border-b-2 transition-colors capitalize"
            style={{ borderColor: filter === c ? "var(--brand-primary)" : "transparent", color: filter === c ? "var(--brand-primary)" : "var(--text-muted)" }}>
            {c === "all" ? "All Documents" : c}
          </button>
        ))}
        <button onClick={() => setShowAdd(!showAdd)} className="px-3 pb-2 text-xs font-medium" style={{ color: "var(--risk-low)" }}>+ Add</button>
      </div>

      {showAdd && (
        <div className="rounded-lg border p-4 mb-4 space-y-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <input placeholder="Title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
          <textarea placeholder="Content..." value={newContent} onChange={(e) => setNewContent(e.target.value)} rows={4} className="w-full text-sm px-3 py-2 rounded border outline-none resize-y" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
          <button onClick={addDoc} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Add</button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((doc, i) => {
          const c = collColor[String(doc.collection)] || collColor.platform;
          return (
            <div key={i} className="rounded-lg border p-4 cursor-pointer transition-colors"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
              onClick={() => setSelectedDoc(doc)}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = c.text; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border)"; }}>
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{String(doc.title)}</h4>
                <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: c.bg, color: c.text }}>{String(doc.collection ?? "")}</span>
              </div>
              <p className="text-xs line-clamp-2" style={{ color: "var(--text-muted)" }}>{String(doc.content_preview ?? "").slice(0, 120)}</p>
            </div>
          );
        })}
        {filtered.length === 0 && <div className="col-span-2 text-center py-12"><p className="text-sm" style={{ color: "var(--text-muted)" }}>{searchQuery ? "No matches" : "No documents"}</p></div>}
      </div>

      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => setSelectedDoc(null)}>
          <div className="w-full max-w-3xl max-h-[80vh] overflow-y-auto rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>{String(selectedDoc.title)}</h3>
              <button onClick={() => setSelectedDoc(null)} style={{ color: "var(--text-muted)" }}>&#10005;</button>
            </div>
            <pre className="whitespace-pre-wrap text-sm" style={{ color: "var(--text-secondary)" }}>{String(selectedDoc.content ?? selectedDoc.content_preview ?? "")}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
