"use client";

import { useState, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function hdrs() {
  const t = typeof window !== "undefined" ? localStorage.getItem("aaop_token") || "" : "";
  const tid = typeof window !== "undefined" ? localStorage.getItem("aaop_tenant_id") || "ott_co" : "ott_co";
  return { Authorization: `Bearer ${t}`, "X-Tenant-ID": tid, "Content-Type": "application/json" };
}

interface TableInfo { table: string; description: string; columns: string[]; db: string; }
interface QueryResult {
  natural_language: string; generated_sql: string; rows: Record<string, unknown>[];
  row_count: number; execution_ms: number; columns: string[]; warnings: string[]; error: string | null;
}

export default function NLQueryPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [examples, setExamples] = useState<string[]>([]);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [showSQL, setShowSQL] = useState(false);
  const [showTables, setShowTables] = useState(false);

  useEffect(() => {
    fetch(`${API}/nl-query/examples`, { headers: hdrs() }).then(r => r.json()).then(setExamples).catch(() => {});
    fetch(`${API}/nl-query/tables`, { headers: hdrs() }).then(r => r.json()).then(setTables).catch(() => {});
  }, []);

  async function run() {
    if (!query.trim()) return;
    setLoading(true); setResult(null);
    try {
      const res = await fetch(`${API}/nl-query/query`, {
        method: "POST", headers: hdrs(), body: JSON.stringify({ natural_language: query, max_rows: 100 }),
      });
      setResult(await res.json());
    } catch { setResult({ natural_language: query, generated_sql: "", rows: [], row_count: 0, execution_ms: 0, columns: [], warnings: [], error: "Connection error" }); }
    setLoading(false);
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Natural Language Query</h1>
      <p className="text-sm" style={{ color: "var(--text-muted)" }}>Ask questions about your platform data in natural language</p>

      {/* Examples */}
      <div className="flex flex-wrap gap-2">
        {examples.slice(0, 6).map((e, i) => (
          <button key={i} onClick={() => setQuery(e)}
            className="text-xs px-3 py-1.5 rounded-full border hover:bg-[var(--background-hover)]"
            style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>{e}</button>
        ))}
      </div>

      {/* Query input */}
      <div className="flex gap-2">
        <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={2}
          placeholder="e.g. Son 7 günün P0 incident'ları"
          className="flex-1 px-4 py-3 rounded-lg text-sm border resize-none"
          style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); run(); } }} />
        <button onClick={run} disabled={loading || !query.trim()}
          className="px-6 py-3 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 self-end">
          {loading ? "Running..." : "Run"}
        </button>
      </div>

      {/* Table browser toggle */}
      <button onClick={() => setShowTables(!showTables)} className="text-xs underline" style={{ color: "var(--text-muted)" }}>
        {showTables ? "Hide" : "Show"} available tables ({tables.length})
      </button>
      {showTables && (
        <div className="rounded-lg border p-3 text-xs space-y-2 max-h-64 overflow-y-auto"
          style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          {tables.map((t) => (
            <div key={t.table}>
              <span className="font-mono font-medium" style={{ color: "var(--brand-primary)" }}>{t.table}</span>
              <span className="ml-2" style={{ color: "var(--text-muted)" }}>— {t.description}</span>
              <div className="ml-4" style={{ color: "var(--text-muted)" }}>{t.columns.join(", ")}</div>
            </div>
          ))}
        </div>
      )}

      {/* Warnings */}
      {result?.warnings?.length ? (
        <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: "rgba(234,179,8,0.1)", color: "#eab308" }}>
          {result.warnings.map((w, i) => <div key={i}>{w}</div>)}
        </div>
      ) : null}

      {/* Error */}
      {result?.error && (
        <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: "rgba(239,68,68,0.1)", color: "#ef4444" }}>
          {result.error}
        </div>
      )}

      {/* Result */}
      {result && !result.error && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              {result.row_count} rows · {result.execution_ms}ms
            </span>
            <button onClick={() => setShowSQL(!showSQL)} className="text-xs underline" style={{ color: "var(--text-muted)" }}>
              {showSQL ? "Hide" : "Show"} SQL
            </button>
          </div>

          {showSQL && (
            <pre className="rounded-lg p-3 text-xs overflow-x-auto font-mono"
              style={{ backgroundColor: "var(--background)", color: "var(--text-secondary)" }}>
              {result.generated_sql}
            </pre>
          )}

          {result.rows.length > 0 && (
            <div className="rounded-lg border overflow-x-auto" style={{ borderColor: "var(--border)" }}>
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ backgroundColor: "var(--background)", borderBottom: "1px solid var(--border)" }}>
                    {result.columns.map((c) => (
                      <th key={c} className="text-left px-3 py-2 font-medium" style={{ color: "var(--text-muted)" }}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.slice(0, 50).map((row, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--background-card)" }}>
                      {result.columns.map((c) => (
                        <td key={c} className="px-3 py-1.5" style={{ color: "var(--text-secondary)" }}>
                          {String(row[c] ?? "—")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
