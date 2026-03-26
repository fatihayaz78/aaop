"use client";

import { useState, useEffect, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ──

interface Source {
  name: string;
  display_name: string;
  description: string;
  group: string;
  status: string;
}

interface SchemaField {
  field_name: string;
  type: string;
  category: string;
  description: string;
  optional: boolean;
}

interface SchemaInfo {
  source_name: string;
  field_count: number;
  categories: string[];
  fields: SchemaField[];
}

interface ValidationCheck {
  name: string;
  status: string;
  detail: string;
}

interface JobStatus {
  job_id: string;
  status: string;
  progress_pct: number;
  files_generated: number;
  elapsed_s: number;
}

interface ExportSchemaItem {
  id: string;
  name: string;
  description: string;
  category: string;
  sources: { source_id: string; fields: string[] }[];
  join_keys: { type: string; left: string; right: string; note: string; window_ms: number | null }[];
  insight: string;
  created_at: string;
}

interface OutputSummary {
  source: string;
  display_name: string;
  file_count: number;
  total_size_mb: number;
}

// ── Source Groups ──

const SOURCE_GROUPS: Record<string, string[]> = {
  CDN: ["medianova", "origin_logs"],
  DRM: ["drm_widevine", "drm_fairplay"],
  QoE: ["player_events", "npaw"],
  Platform: ["api_logs", "newrelic"],
  Business: ["crm", "epg", "billing", "push_notifications", "app_reviews"],
};

export default function MockDataGenPage() {
  const [tab, setTab] = useState<"generator" | "schema" | "export">("generator");

  return (
    <div className="p-6 space-y-6 min-h-screen" style={{ background: "var(--background)" }}>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
          Data Generation & Extraction
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => setTab("generator")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === "generator"
                ? "text-white"
                : "hover:opacity-80"
            }`}
            style={{
              background: tab === "generator" ? "var(--brand-primary)" : "var(--background-card)",
              color: tab === "generator" ? "#fff" : "var(--text-secondary)",
              border: `1px solid ${tab === "generator" ? "var(--brand-primary)" : "var(--border)"}`,
            }}
          >
            Generator
          </button>
          <button
            onClick={() => setTab("schema")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === "schema"
                ? "text-white"
                : "hover:opacity-80"
            }`}
            style={{
              background: tab === "schema" ? "var(--brand-primary)" : "var(--background-card)",
              color: tab === "schema" ? "#fff" : "var(--text-secondary)",
              border: `1px solid ${tab === "schema" ? "var(--brand-primary)" : "var(--border)"}`,
            }}
          >
            Schema Browser
          </button>
          <button
            onClick={() => setTab("export")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === "export"
                ? "text-white"
                : "hover:opacity-80"
            }`}
            style={{
              background: tab === "export" ? "var(--brand-primary)" : "var(--background-card)",
              color: tab === "export" ? "#fff" : "var(--text-secondary)",
              border: `1px solid ${tab === "export" ? "var(--brand-primary)" : "var(--border)"}`,
            }}
          >
            Export Schema
          </button>
        </div>
      </div>

      {tab === "generator" ? <GeneratorTab /> : tab === "schema" ? <SchemaBrowserTab /> : <ExportSchemaTab />}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// GENERATOR TAB
// ══════════════════════════════════════════════════════════════════════

function GeneratorTab() {
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [startDate, setStartDate] = useState("2026-03-04");
  const [endDate, setEndDate] = useState("2026-03-04");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [outputSummary, setOutputSummary] = useState<OutputSummary[]>([]);
  const [validationResults, setValidationResults] = useState<ValidationCheck[]>([]);
  const [generating, setGenerating] = useState(false);
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    fetch(`${API}/mock-data-gen/sources`)
      .then((r) => r.json())
      .then(setSources)
      .catch(() => {});
  }, []);

  const toggleSource = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const selectGroup = (group: string) => {
    const groupSources = SOURCE_GROUPS[group] || [];
    setSelected((prev) => {
      const next = new Set(prev);
      const allSelected = groupSources.every((s) => next.has(s));
      groupSources.forEach((s) => (allSelected ? next.delete(s) : next.add(s)));
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === sources.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(sources.map((s) => s.name)));
    }
  };

  const handleGenerate = async () => {
    if (selected.size === 0) return;
    setGenerating(true);
    setJobStatus(null);
    try {
      const res = await fetch(`${API}/mock-data-gen/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sources: Array.from(selected),
          start_date: startDate,
          end_date: endDate,
        }),
      });
      const data = await res.json();
      setJobId(data.job_id);
    } catch {
      setGenerating(false);
    }
  };

  // Poll job status
  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/mock-data-gen/jobs/${jobId}`);
        const data: JobStatus = await res.json();
        setJobStatus(data);
        if (data.status === "done" || data.status === "failed") {
          clearInterval(interval);
          setGenerating(false);
          // Refresh output summary
          fetch(`${API}/mock-data-gen/output/summary`)
            .then((r) => r.json())
            .then(setOutputSummary)
            .catch(() => {});
        }
      } catch {
        clearInterval(interval);
        setGenerating(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId]);

  const handleValidate = async () => {
    setValidating(true);
    try {
      const res = await fetch(`${API}/mock-data-gen/validate`, { method: "POST" });
      const data = await res.json();
      setValidationResults(data.checks || []);
    } catch {
      /* ignore */
    }
    setValidating(false);
  };

  return (
    <div className="space-y-6">
      {/* Source selector */}
      <div className="rounded-lg p-4" style={{ background: "var(--background-card)", border: "1px solid var(--border)" }}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            Data Sources
          </h3>
          <button
            onClick={selectAll}
            className="text-xs px-3 py-1 rounded"
            style={{ background: "var(--background-hover)", color: "var(--text-secondary)" }}
          >
            {selected.size === sources.length ? "Deselect All" : "Select All"}
          </button>
        </div>

        {Object.entries(SOURCE_GROUPS).map(([group, groupSources]) => (
          <div key={group} className="mb-3">
            <button
              onClick={() => selectGroup(group)}
              className="text-xs font-medium mb-1 px-2 py-0.5 rounded"
              style={{ background: "var(--brand-glow)", color: "var(--brand-primary)" }}
            >
              {group}
            </button>
            <div className="flex flex-wrap gap-2 mt-1">
              {groupSources.map((sName) => {
                const src = sources.find((s) => s.name === sName);
                const isSelected = selected.has(sName);
                return (
                  <label
                    key={sName}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg cursor-pointer text-sm transition"
                    style={{
                      background: isSelected ? "var(--brand-glow)" : "var(--background-hover)",
                      border: `1px solid ${isSelected ? "var(--brand-primary)" : "var(--border)"}`,
                      color: isSelected ? "var(--brand-primary)" : "var(--text-secondary)",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSource(sName)}
                      className="accent-blue-500"
                    />
                    {src?.display_name || sName}
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Date range + Generate */}
      <div className="flex items-end gap-4">
        <div>
          <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm"
            style={{ background: "var(--background-card)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
        </div>
        <div>
          <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm"
            style={{ background: "var(--background-card)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating || selected.size === 0}
          className="px-6 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--brand-primary)" }}
        >
          {generating ? "Generating..." : "Generate"}
        </button>
        {jobStatus && jobStatus.status === "running" && (
          <button
            onClick={async () => {
              if (!jobId) return;
              try {
                await fetch(`${API}/mock-data-gen/jobs/${jobId}/cancel`, { method: "POST" });
                setJobStatus((prev) => prev ? { ...prev, status: "cancelled", progress_pct: prev.progress_pct } : null);
                setGenerating(false);
              } catch { /* ignore */ }
            }}
            className="px-6 py-2 rounded-lg text-sm font-medium text-white"
            style={{ background: "var(--status-error)" }}
          >
            Stop
          </button>
        )}
        <button
          onClick={handleValidate}
          disabled={validating}
          className="px-6 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--background-card)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
        >
          {validating ? "Validating..." : "Validate"}
        </button>
      </div>

      {/* Progress bar */}
      {jobStatus && (
        <div className="rounded-lg p-4" style={{ background: "var(--background-card)", border: "1px solid var(--border)" }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm" style={{ color: "var(--text-primary)" }}>
              Job: {jobStatus.job_id} — {jobStatus.status}
            </span>
            <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
              {jobStatus.elapsed_s}s
            </span>
          </div>
          <div className="w-full rounded-full h-2" style={{ background: "var(--background-hover)" }}>
            <div
              className="h-2 rounded-full transition-all"
              style={{
                width: `${jobStatus.progress_pct}%`,
                background: jobStatus.status === "failed" ? "var(--status-error)" : "var(--brand-primary)",
              }}
            />
          </div>
        </div>
      )}

      {/* Output summary */}
      {outputSummary.length > 0 && (
        <div className="rounded-lg p-4" style={{ background: "var(--background-card)", border: "1px solid var(--border)" }}>
          <h3 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Output Summary</h3>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--text-secondary)", borderBottom: "1px solid var(--border)" }}>
                <th className="text-left py-2">Source</th>
                <th className="text-right py-2">Files</th>
                <th className="text-right py-2">Size (MB)</th>
              </tr>
            </thead>
            <tbody>
              {outputSummary.map((s) => (
                <tr key={s.source} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="py-2" style={{ color: "var(--text-primary)" }}>{s.display_name}</td>
                  <td className="text-right py-2" style={{ color: "var(--text-secondary)" }}>{s.file_count}</td>
                  <td className="text-right py-2" style={{ color: "var(--text-secondary)" }}>{s.total_size_mb}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Validation results */}
      {validationResults.length > 0 && (
        <div className="rounded-lg p-4" style={{ background: "var(--background-card)", border: "1px solid var(--border)" }}>
          <h3 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Validation Results</h3>
          <div className="space-y-2">
            {validationResults.map((check) => (
              <div
                key={check.name}
                className="flex items-center justify-between p-3 rounded-lg"
                style={{ background: "var(--background-hover)" }}
              >
                <div>
                  <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                    {check.name.replace(/_/g, " ")}
                  </span>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>{check.detail}</p>
                </div>
                <span
                  className="px-2 py-1 rounded text-xs font-medium"
                  style={{
                    background: check.status === "pass" ? "var(--risk-low-bg)" :
                      check.status === "skip" ? "var(--risk-medium-bg)" : "var(--risk-high-bg)",
                    color: check.status === "pass" ? "var(--risk-low)" :
                      check.status === "skip" ? "var(--risk-medium)" : "var(--risk-high)",
                  }}
                >
                  {check.status.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// SCHEMA BROWSER TAB
// ══════════════════════════════════════════════════════════════════════

function SchemaBrowserTab() {
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>("medianova");
  const [schema, setSchema] = useState<SchemaInfo | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  useEffect(() => {
    fetch(`${API}/mock-data-gen/sources`)
      .then((r) => r.json())
      .then(setSources)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetch(`${API}/mock-data-gen/sources/${selectedSource}/schema`)
      .then((r) => r.json())
      .then((data: SchemaInfo) => {
        setSchema(data);
        setCategoryFilter("all");
      })
      .catch(() => {});
  }, [selectedSource]);

  const filteredFields = schema?.fields.filter(
    (f) => categoryFilter === "all" || f.category === categoryFilter
  ) || [];

  const handleExport = () => {
    if (!schema) return;
    const blob = new Blob([JSON.stringify(schema, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedSource}_schema.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* Source selector + category filter */}
      <div className="flex items-center gap-4">
        <div>
          <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>Source</label>
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm"
            style={{ background: "var(--background-card)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            {sources.map((s) => (
              <option key={s.name} value={s.name}>{s.display_name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>Category</label>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm"
            style={{ background: "var(--background-card)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            <option value="all">All Categories</option>
            {schema?.categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div className="ml-auto mt-5">
          <button
            onClick={handleExport}
            className="px-4 py-2 rounded-lg text-sm"
            style={{ background: "var(--background-card)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
          >
            Export Schema JSON
          </button>
        </div>
      </div>

      {/* Field count */}
      {schema && (
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {filteredFields.length} / {schema.field_count} fields
          {categoryFilter !== "all" && ` in "${categoryFilter}"`}
        </p>
      )}

      {/* Field table */}
      <div className="rounded-lg overflow-hidden" style={{ background: "var(--background-card)", border: "1px solid var(--border)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: "var(--background-hover)", color: "var(--text-secondary)" }}>
              <th className="text-left px-4 py-3">Field Name</th>
              <th className="text-left px-4 py-3">Type</th>
              <th className="text-left px-4 py-3">Category</th>
              <th className="text-left px-4 py-3">Description</th>
              <th className="text-center px-4 py-3">Optional</th>
            </tr>
          </thead>
          <tbody>
            {filteredFields.map((f) => (
              <tr key={f.field_name} style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="px-4 py-2 font-mono text-xs" style={{ color: "var(--brand-primary)" }}>
                  {f.field_name}
                </td>
                <td className="px-4 py-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                  {f.type}
                </td>
                <td className="px-4 py-2">
                  <span
                    className="text-xs px-2 py-0.5 rounded"
                    style={{ background: "var(--brand-glow)", color: "var(--brand-primary)" }}
                  >
                    {f.category}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs" style={{ color: "var(--text-primary)" }}>
                  {f.description}
                </td>
                <td className="px-4 py-2 text-center text-xs" style={{ color: "var(--text-secondary)" }}>
                  {f.optional ? "Yes" : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// EXPORT SCHEMA TAB
// ══════════════════════════════════════════════════════════════════════

const CATEGORY_COLORS: Record<string, { bg: string; color: string }> = {
  CDN: { bg: "rgba(31,111,235,0.15)", color: "#1f6feb" },
  QoE: { bg: "rgba(35,134,54,0.15)", color: "#238636" },
  DRM: { bg: "rgba(210,153,34,0.15)", color: "#d29922" },
  Business: { bg: "rgba(218,54,51,0.15)", color: "#da3633" },
  Platform: { bg: "rgba(139,148,158,0.15)", color: "#8b949e" },
};

const ALL_SOURCES_FOR_EXPORT = [
  "medianova_cdn", "origin_server", "widevine_drm", "fairplay_drm",
  "player_events", "npaw_analytics", "api_logs", "newrelic_apm",
  "crm_subscriber", "epg", "billing", "push_notifications", "app_reviews",
];

function ExportSchemaTab() {
  const [schemas, setSchemas] = useState<ExportSchemaItem[]>([]);
  const [selected, setSelected] = useState<ExportSchemaItem | null>(null);
  const [mode, setMode] = useState<"view" | "new">("view");
  const [sqlModal, setSqlModal] = useState<string | null>(null);

  // New schema form state
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formCategory, setFormCategory] = useState("CDN");
  const [formSources, setFormSources] = useState<Set<string>>(new Set());
  const [formStep, setFormStep] = useState(1);
  const [previewKeys, setPreviewKeys] = useState<ExportSchemaItem["join_keys"]>([]);
  const [formFields, setFormFields] = useState<Record<string, Set<string>>>({});
  const [sourceSchemas, setSourceSchemas] = useState<Record<string, SchemaField[]>>({});

  const loadSchemas = () => {
    fetch(`${API}/mock-data-gen/schemas`).then(r => r.json()).then(setSchemas).catch(() => {});
  };

  useEffect(() => { loadSchemas(); }, []);

  // Preview join keys when sources change
  useEffect(() => {
    if (formSources.size < 2) { setPreviewKeys([]); return; }
    const sources = Array.from(formSources).map(s => ({ source_id: s, fields: [] }));
    fetch(`${API}/mock-data-gen/schemas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "_preview", description: "", category: formCategory, sources }),
    }).then(r => r.json()).then(data => {
      setPreviewKeys(data.join_keys || []);
      // Clean up preview schema
      if (data.id) fetch(`${API}/mock-data-gen/schemas/${data.id}`, { method: "DELETE" });
    }).catch(() => {});
  }, [formSources, formCategory]);

  // Load field schemas for step 2
  useEffect(() => {
    if (formStep !== 2) return;
    const mapping: Record<string, string> = {
      medianova_cdn: "medianova", origin_server: "origin_logs",
      widevine_drm: "drm_widevine", fairplay_drm: "drm_fairplay",
      player_events: "player_events", npaw_analytics: "npaw",
      api_logs: "api_logs", newrelic_apm: "newrelic",
      crm_subscriber: "crm", epg: "epg", billing: "billing",
      push_notifications: "push_notifications", app_reviews: "app_reviews",
    };
    Array.from(formSources).forEach(srcId => {
      const apiName = mapping[srcId] || srcId;
      if (!sourceSchemas[srcId]) {
        fetch(`${API}/mock-data-gen/sources/${apiName}/schema`)
          .then(r => r.json())
          .then(data => {
            setSourceSchemas(prev => ({ ...prev, [srcId]: data.fields || [] }));
            // Pre-check join key fields
            const jkFields = new Set<string>();
            previewKeys.forEach(jk => {
              if (jk.left.startsWith(srcId + ".")) jkFields.add(jk.left.split(".")[1]);
              if (jk.right.startsWith(srcId + ".")) jkFields.add(jk.right.split(".")[1]);
            });
            setFormFields(prev => ({ ...prev, [srcId]: new Set(Array.from(jkFields)) }));
          }).catch(() => {});
      }
    });
  }, [formStep, formSources, previewKeys, sourceSchemas]);

  const toggleFormSource = (s: string) => {
    setFormSources(prev => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s); else next.add(s);
      return next;
    });
  };

  const toggleField = (srcId: string, field: string) => {
    setFormFields(prev => {
      const current = new Set(prev[srcId] || []);
      if (current.has(field)) current.delete(field); else current.add(field);
      return { ...prev, [srcId]: current };
    });
  };

  const isJoinKeyField = (srcId: string, field: string) => {
    return previewKeys.some(jk =>
      jk.left === `${srcId}.${field}` || jk.right === `${srcId}.${field}`
    );
  };

  const handleSave = async () => {
    const sources = Array.from(formSources).map(s => ({
      source_id: s,
      fields: Array.from(formFields[s] || []),
    }));
    const res = await fetch(`${API}/mock-data-gen/schemas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: formName, description: formDesc, category: formCategory, sources }),
    });
    const data = await res.json();
    loadSchemas();
    setSelected(data);
    setMode("view");
    setFormStep(1);
    setFormName(""); setFormDesc(""); setFormSources(new Set()); setFormFields({});
  };

  const handleExportSQL = async (id: string) => {
    const res = await fetch(`${API}/mock-data-gen/schemas/${id}/export/sql`);
    const data = await res.json();
    setSqlModal(data.sql || "-- No SQL generated");
  };

  const handleDownloadJSON = (schema: ExportSchemaItem) => {
    const blob = new Blob([JSON.stringify(schema, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `${schema.name}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  const catBadge = (cat: string) => {
    const c = CATEGORY_COLORS[cat] || CATEGORY_COLORS.Platform;
    return <span className="text-xs px-2 py-0.5 rounded" style={{ background: c.bg, color: c.color }}>{cat}</span>;
  };

  return (
    <div className="flex gap-4" style={{ minHeight: "calc(100vh - 200px)" }}>
      {/* LEFT PANEL */}
      <div className="flex-shrink-0" style={{ width: 280, background: "var(--background-card)", border: "1px solid var(--border)", borderRadius: 8, padding: 12 }}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Saved schemas</span>
          <button onClick={() => { setMode("new"); setSelected(null); setFormStep(1); }} className="text-xs px-2 py-1 rounded" style={{ background: "var(--brand-primary)", color: "#fff" }}>+ New schema</button>
        </div>
        <div className="space-y-2">
          {schemas.map(s => (
            <div
              key={s.id}
              onClick={() => { setSelected(s); setMode("view"); }}
              className="p-2 rounded-lg cursor-pointer transition"
              style={{
                background: selected?.id === s.id ? "var(--brand-glow)" : "var(--background-hover)",
                border: `1px solid ${selected?.id === s.id ? "var(--brand-primary)" : "transparent"}`,
              }}
            >
              <div className="text-sm" style={{ color: "var(--text-primary)", fontWeight: 500 }}>{s.name}</div>
              <div className="flex items-center gap-2 mt-1">
                {catBadge(s.category)}
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>{s.sources.length} sources · {s.join_keys.length} join keys</span>
              </div>
            </div>
          ))}
          {schemas.length === 0 && <p className="text-xs" style={{ color: "var(--text-muted)" }}>No schemas yet</p>}
        </div>
      </div>

      {/* RIGHT PANEL */}
      <div className="flex-1 rounded-lg" style={{ background: "var(--background-card)", border: "1px solid var(--border)", padding: 16 }}>
        {mode === "view" && selected ? (
          <div className="space-y-5">
            {/* Header */}
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>{selected.name}</h2>
                {catBadge(selected.category)}
              </div>
              <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>{selected.description}</p>
            </div>

            {/* Sources & fields */}
            <div>
              <h3 className="text-sm font-medium mb-2" style={{ color: "var(--text-primary)" }}>Sources & fields</h3>
              {selected.sources.map(src => (
                <details key={src.source_id} className="mb-2">
                  <summary className="text-sm cursor-pointer py-1 px-2 rounded" style={{ background: "var(--background-hover)", color: "var(--text-primary)" }}>
                    {src.source_id} <span className="text-xs" style={{ color: "var(--text-muted)" }}>({src.fields.length} fields)</span>
                  </summary>
                  <div className="flex flex-wrap gap-1 mt-1 pl-4">
                    {src.fields.map(f => {
                      const isJK = selected.join_keys.some(jk => jk.left.endsWith(`.${f}`) || jk.right.endsWith(`.${f}`));
                      return (
                        <span key={f} className="text-xs px-2 py-0.5 rounded" style={{
                          background: isJK ? "rgba(31,111,235,0.15)" : "var(--background-hover)",
                          color: isJK ? "var(--brand-primary)" : "var(--text-secondary)",
                          border: isJK ? "1px solid var(--brand-primary)" : "1px solid transparent",
                        }}>{f}</span>
                      );
                    })}
                  </div>
                </details>
              ))}
            </div>

            {/* Join keys */}
            <div>
              <h3 className="text-sm font-medium mb-2" style={{ color: "var(--text-primary)" }}>Join keys — auto-detected</h3>
              <div className="space-y-1">
                {selected.join_keys.map((jk, i) => {
                  const typeBg = jk.type === "exact" ? "rgba(31,111,235,0.15)" : jk.type === "window" ? "rgba(210,153,34,0.15)" : "rgba(139,148,158,0.15)";
                  const typeColor = jk.type === "exact" ? "#1f6feb" : jk.type === "window" ? "#d29922" : "#8b949e";
                  return (
                    <div key={i} className="flex items-center gap-2 p-2 rounded text-xs" style={{ background: "var(--background-hover)" }}>
                      <span className="px-1.5 py-0.5 rounded" style={{ background: typeBg, color: typeColor }}>{jk.type}</span>
                      <span style={{ color: "var(--text-primary)" }}>{jk.left}</span>
                      <span style={{ color: "var(--text-muted)" }}>&rarr;</span>
                      <span style={{ color: "var(--text-primary)" }}>{jk.right}</span>
                      <span className="ml-auto" style={{ color: "var(--text-muted)" }}>{jk.note}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Insight */}
            <div className="pl-3" style={{ borderLeft: "2px solid var(--brand-primary)" }}>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{selected.insight}</p>
            </div>

            {/* Action bar */}
            <div className="flex gap-2 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
              <button onClick={() => handleExportSQL(selected.id)} className="px-4 py-2 rounded-lg text-sm" style={{ background: "var(--brand-primary)", color: "#fff" }}>Export SQL</button>
              <button onClick={() => handleDownloadJSON(selected)} className="px-4 py-2 rounded-lg text-sm" style={{ background: "var(--background-hover)", color: "var(--text-primary)", border: "1px solid var(--border)" }}>Download JSON</button>
              <button onClick={() => { setMode("new"); setFormName(selected.name); setFormDesc(selected.description); setFormCategory(selected.category); setFormSources(new Set(selected.sources.map(s => s.source_id))); setFormStep(1); }} className="px-4 py-2 rounded-lg text-sm" style={{ background: "var(--background-hover)", color: "var(--text-primary)", border: "1px solid var(--border)" }}>Edit</button>
            </div>
          </div>
        ) : mode === "new" ? (
          <div className="space-y-4">
            {formStep === 1 ? (
              <>
                <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>New Export Schema — Step 1</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>Name *</label>
                    <input value={formName} onChange={e => setFormName(e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm" style={{ background: "var(--background-hover)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>Description</label>
                    <textarea value={formDesc} onChange={e => setFormDesc(e.target.value)} rows={2} className="w-full px-3 py-2 rounded-lg text-sm" style={{ background: "var(--background-hover)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>Category</label>
                    <select value={formCategory} onChange={e => setFormCategory(e.target.value)} className="px-3 py-2 rounded-lg text-sm" style={{ background: "var(--background-hover)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                      {["CDN", "QoE", "DRM", "Business", "Platform"].map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs mb-2" style={{ color: "var(--text-secondary)" }}>Sources</label>
                    <div className="grid grid-cols-2 gap-2">
                      {ALL_SOURCES_FOR_EXPORT.map(s => (
                        <label key={s} className="flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer text-xs" style={{
                          background: formSources.has(s) ? "var(--brand-glow)" : "var(--background-hover)",
                          border: `1px solid ${formSources.has(s) ? "var(--brand-primary)" : "var(--border)"}`,
                          color: formSources.has(s) ? "var(--brand-primary)" : "var(--text-secondary)",
                        }}>
                          <input type="checkbox" checked={formSources.has(s)} onChange={() => toggleFormSource(s)} className="accent-blue-500" />
                          {s}
                        </label>
                      ))}
                    </div>
                  </div>
                  {previewKeys.length > 0 && (
                    <div>
                      <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>Auto-detected join keys:</p>
                      {previewKeys.map((jk, i) => (
                        <div key={i} className="text-xs px-2 py-1 rounded mb-1" style={{ background: "var(--background-hover)", color: "var(--text-secondary)" }}>
                          <span style={{ color: jk.type === "exact" ? "#1f6feb" : "#d29922" }}>[{jk.type}]</span> {jk.left} &rarr; {jk.right}
                        </div>
                      ))}
                    </div>
                  )}
                  <button disabled={!formName || formSources.size === 0} onClick={() => setFormStep(2)} className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50" style={{ background: "var(--brand-primary)" }}>Continue &rarr;</button>
                </div>
              </>
            ) : (
              <>
                <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>New Export Schema — Step 2: Select Fields</h3>
                <div className="space-y-3">
                  {Array.from(formSources).map(srcId => {
                    const fields = sourceSchemas[srcId] || [];
                    return (
                      <div key={srcId}>
                        <p className="text-sm font-medium mb-1" style={{ color: "var(--text-primary)" }}>{srcId}</p>
                        <div className="flex flex-wrap gap-1">
                          {fields.map(f => {
                            const isJK = isJoinKeyField(srcId, f.field_name);
                            const checked = formFields[srcId]?.has(f.field_name) || false;
                            return (
                              <label key={f.field_name} className="flex items-center gap-1 text-xs px-2 py-1 rounded cursor-pointer" style={{
                                background: isJK ? "rgba(31,111,235,0.15)" : checked ? "var(--brand-glow)" : "var(--background-hover)",
                                color: isJK ? "var(--brand-primary)" : "var(--text-secondary)",
                                border: `1px solid ${isJK ? "var(--brand-primary)" : "transparent"}`,
                              }}>
                                <input type="checkbox" checked={checked || isJK} disabled={isJK} onChange={() => toggleField(srcId, f.field_name)} className="accent-blue-500" />
                                {f.field_name}
                              </label>
                            );
                          })}
                          {fields.length === 0 && <span className="text-xs" style={{ color: "var(--text-muted)" }}>Loading...</span>}
                        </div>
                      </div>
                    );
                  })}
                  <div className="flex gap-2">
                    <button onClick={() => setFormStep(1)} className="px-4 py-2 rounded-lg text-sm" style={{ background: "var(--background-hover)", color: "var(--text-primary)", border: "1px solid var(--border)" }}>&larr; Back</button>
                    <button onClick={handleSave} className="px-4 py-2 rounded-lg text-sm font-medium text-white" style={{ background: "var(--brand-primary)" }}>Save Schema</button>
                  </div>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>Select a schema or create a new one</p>
          </div>
        )}
      </div>

      {/* SQL Modal */}
      {sqlModal !== null && (
        <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
          <div className="rounded-lg p-6" style={{ background: "var(--background-card)", border: "1px solid var(--border)", maxWidth: 700, width: "100%", minHeight: 400, maxHeight: "80vh", overflow: "auto" }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>DuckDB SQL</h3>
              <div className="flex gap-2">
                <button onClick={() => navigator.clipboard.writeText(sqlModal)} className="px-3 py-1 rounded text-xs" style={{ background: "var(--brand-primary)", color: "#fff" }}>Copy</button>
                <button onClick={() => setSqlModal(null)} className="px-3 py-1 rounded text-xs" style={{ background: "var(--background-hover)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>Close</button>
              </div>
            </div>
            <pre className="text-xs p-4 rounded overflow-x-auto" style={{ background: "var(--background)", color: "var(--text-primary)", fontFamily: "var(--font-mono)", whiteSpace: "pre-wrap" }}>{sqlModal}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
