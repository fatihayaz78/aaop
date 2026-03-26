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
  const [tab, setTab] = useState<"generator" | "schema">("generator");

  return (
    <div className="p-6 space-y-6 min-h-screen" style={{ background: "var(--background)" }}>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
          Mock Data Generator
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
        </div>
      </div>

      {tab === "generator" ? <GeneratorTab /> : <SchemaBrowserTab />}
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
