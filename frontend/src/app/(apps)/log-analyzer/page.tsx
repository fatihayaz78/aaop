"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost, apiDelete } from "@/lib/api";
import type { LogProject, FetchJob, AnalysisResult } from "@/types";

type Tab = "projects" | "akamai" | "results";

const CHART_TYPES = [
  "error_rate", "bandwidth", "cache_hit_ratio", "origin_offload", "latency_p99",
  "requests_per_second", "status_codes", "top_ips", "top_urls", "geographic_distribution",
  "cdn_provider_comparison", "time_to_first_byte", "player_startup",
  "bitrate_distribution", "rebuffer_rate", "error_type_breakdown",
  "throughput_trend", "peak_concurrent", "edge_server_load",
  "protocol_distribution", "ssl_handshake_time",
];

export default function LogAnalyzer() {
  const [tab, setTab] = useState<Tab>("projects");
  const [projects, setProjects] = useState<LogProject[]>([]);
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectModule, setNewProjectModule] = useState("akamai");

  // Akamai tab state
  const [akamaiConfig, setAkamaiConfig] = useState({ s3_bucket: "ssport-datastream", s3_prefix: "logs/", schedule_cron: "0 */6 * * *" });
  const [fetchJob, setFetchJob] = useState<FetchJob | null>(null);
  const [chartsData, setChartsData] = useState<Record<string, Record<string, unknown>[]>>({});
  const [expandedResult, setExpandedResult] = useState<AnalysisResult | null>(null);

  const loadProjects = useCallback(async () => {
    try {
      const p = await apiGet<LogProject[]>("/log-analyzer/projects?tenant_id=bein_sports");
      setProjects(p);
    } catch { /* backend offline */ }
  }, []);

  const loadResults = useCallback(async () => {
    try {
      const r = await apiGet<AnalysisResult[]>("/log-analyzer/results?tenant_id=bein_sports&limit=20");
      setResults(r);
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => { loadProjects(); loadResults(); }, [loadProjects, loadResults]);

  const createProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      await apiPost("/log-analyzer/projects", {
        tenant_id: "bein_sports",
        name: newProjectName,
        sub_module: newProjectModule,
      });
      setNewProjectName("");
      setShowNewProject(false);
      loadProjects();
    } catch { /* error */ }
  };

  const deleteProject = async (id: string) => {
    if (!confirm("Delete this project?")) return;
    try {
      await apiDelete(`/log-analyzer/projects/${id}`);
      loadProjects();
    } catch { /* error */ }
  };

  const configureAkamai = async () => {
    try {
      await apiPost("/log-analyzer/akamai/configure", { tenant_id: "bein_sports", ...akamaiConfig, enabled: true });
    } catch { /* error */ }
  };

  const fetchLogs = async () => {
    try {
      const job = await apiPost<FetchJob>("/log-analyzer/akamai/fetch", { tenant_id: "bein_sports" });
      setFetchJob(job);
      pollJob(job.jobId);
    } catch { /* error */ }
  };

  const pollJob = (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const job = await apiGet<FetchJob>(`/log-analyzer/akamai/jobs/${jobId}`);
        setFetchJob(job);
        if (job.status === "completed" || job.status === "failed") {
          clearInterval(interval);
          if (job.status === "completed") loadCharts(jobId);
        }
      } catch { clearInterval(interval); }
    }, 5000);
  };

  const loadCharts = async (jobId: string) => {
    const data: Record<string, Record<string, unknown>[]> = {};
    for (const ct of CHART_TYPES) {
      try {
        const cd = await apiGet<{ data: Record<string, unknown>[] }>(`/log-analyzer/akamai/charts?job_id=${jobId}&chart_type=${ct}`);
        data[ct] = cd.data;
      } catch {
        data[ct] = [];
      }
    }
    setChartsData(data);
  };

  const downloadReport = async () => {
    try {
      await apiPost("/log-analyzer/akamai/report", { tenant_id: "bein_sports" });
    } catch { /* error */ }
  };

  const TABS: { key: Tab; label: string }[] = [
    { key: "projects", label: "Projects" },
    { key: "akamai", label: "Akamai Analyzer" },
    { key: "results", label: "Analysis Results" },
  ];

  const jobProgress = fetchJob?.status === "completed" ? 100 : fetchJob?.status === "running" ? (fetchJob.progress ?? 50) : fetchJob?.status === "queued" ? 10 : 0;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Log Analyzer</h2>

      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Projects */}
      {tab === "projects" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{projects.length} project(s)</p>
            <button onClick={() => setShowNewProject(true)}
              className="px-4 py-1.5 rounded text-sm font-medium"
              style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
              + New Project
            </button>
          </div>

          {/* Project cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((p) => (
              <div key={p.projectId} className="rounded-lg border p-4"
                style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{p.name}</h4>
                  <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>{p.subModule}</span>
                </div>
                <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>Status: {p.status} | Created: {p.createdAt}</p>
                <div className="flex gap-2">
                  <button className="text-xs px-2 py-1 rounded border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Edit</button>
                  <button onClick={() => deleteProject(p.projectId)} className="text-xs px-2 py-1 rounded" style={{ color: "var(--risk-high)" }}>Delete</button>
                </div>
              </div>
            ))}
            {projects.length === 0 && (
              <div className="col-span-3 rounded-lg border p-8 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>No projects. Create one to start analyzing logs.</p>
              </div>
            )}
          </div>

          {/* New Project Sheet */}
          {showNewProject && (
            <div className="fixed inset-0 z-50 flex justify-end" style={{ backgroundColor: "rgba(0,0,0,0.5)" }} onClick={() => setShowNewProject(false)}>
              <div className="w-96 h-full p-6 overflow-y-auto" style={{ backgroundColor: "var(--background-card)" }} onClick={(e) => e.stopPropagation()}>
                <h3 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>New Project</h3>
                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Project Name</label>
                    <input type="text" value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)}
                      className="w-full text-sm px-3 py-2 rounded border outline-none"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}
                      placeholder="My Akamai Analysis" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Sub-Module</label>
                    <select value={newProjectModule} onChange={(e) => setNewProjectModule(e.target.value)}
                      className="w-full text-sm px-3 py-2 rounded border"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      <option value="akamai">Akamai DS2</option>
                      <option value="medianova" disabled>Medianova (Coming Soon)</option>
                    </select>
                  </div>
                  <div className="flex gap-2 pt-4">
                    <button onClick={createProject} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Create</button>
                    <button onClick={() => setShowNewProject(false)} className="px-4 py-2 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Akamai Analyzer */}
      {tab === "akamai" && (
        <div>
          {/* Config form */}
          <div className="rounded-lg border p-4 mb-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Akamai DataStream 2 Configuration</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>S3 Bucket</label>
                <input type="text" value={akamaiConfig.s3_bucket} onChange={(e) => setAkamaiConfig({ ...akamaiConfig, s3_bucket: e.target.value })}
                  className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                  style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>S3 Prefix</label>
                <input type="text" value={akamaiConfig.s3_prefix} onChange={(e) => setAkamaiConfig({ ...akamaiConfig, s3_prefix: e.target.value })}
                  className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                  style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Schedule (Cron)</label>
                <input type="text" value={akamaiConfig.schedule_cron} onChange={(e) => setAkamaiConfig({ ...akamaiConfig, schedule_cron: e.target.value })}
                  className="w-full text-sm px-3 py-1.5 rounded border outline-none font-mono"
                  style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={configureAkamai} className="px-4 py-1.5 rounded text-sm font-medium border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Save Config</button>
              <button onClick={fetchLogs} disabled={fetchJob?.status === "running"} className="px-4 py-1.5 rounded text-sm font-medium disabled:opacity-50" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Fetch Logs</button>
              <button onClick={downloadReport} className="px-4 py-1.5 rounded text-sm font-medium border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Download Report (DOCX)</button>
            </div>
          </div>

          {/* Job progress */}
          {fetchJob && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Job: {fetchJob.jobId}</span>
                <span className="text-xs" style={{ color: fetchJob.status === "completed" ? "var(--risk-low)" : fetchJob.status === "failed" ? "var(--risk-high)" : "var(--brand-primary)" }}>
                  {fetchJob.status}
                </span>
              </div>
              <div className="w-full h-2 rounded-full" style={{ backgroundColor: "var(--border)" }}>
                <div className="h-2 rounded-full transition-all" style={{ width: `${jobProgress}%`, backgroundColor: fetchJob.status === "failed" ? "var(--risk-high)" : "var(--brand-primary)" }} />
              </div>
            </div>
          )}

          {/* 21 Charts grid */}
          {Object.keys(chartsData).length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {CHART_TYPES.map((ct) => (
                <div key={ct} className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                  <RechartsWrapper
                    data={chartsData[ct] ?? []}
                    xKey="time"
                    yKey="value"
                    title={ct.replace(/_/g, " ")}
                    height={180}
                    type={["status_codes", "top_ips", "top_urls", "geographic_distribution", "protocol_distribution"].includes(ct) ? "bar" : "line"}
                  />
                </div>
              ))}
            </div>
          )}

          {Object.keys(chartsData).length === 0 && !fetchJob && (
            <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>Configure and fetch logs to see 21 analysis charts.</p>
            </div>
          )}
        </div>
      )}

      {/* Tab: Analysis Results */}
      {tab === "results" && (
        <div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable
              columns={[
                { key: "analysisId", label: "Analysis ID" },
                { key: "projectId", label: "Project" },
                { key: "jobId", label: "Job ID" },
                { key: "errorRate", label: "Error Rate", render: (v) => <span>{((v as number) * 100).toFixed(2)}%</span> },
                { key: "anomalies", label: "Anomalies", render: (v) => <span>{(v as unknown[])?.length ?? 0}</span> },
                { key: "createdAt", label: "Analyzed At" },
              ]}
              data={results as unknown as Record<string, unknown>[]}
              onRowClick={(row) => setExpandedResult(row as unknown as AnalysisResult)}
            />
          </div>

          {expandedResult && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.6)" }} onClick={() => setExpandedResult(null)}>
              <div className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-lg border p-6"
                style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
                <div className="flex justify-between mb-4">
                  <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Analysis Detail</h3>
                  <button onClick={() => setExpandedResult(null)} style={{ color: "var(--text-muted)" }}>✕</button>
                </div>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <MetricCard title="Error Rate" value={`${(expandedResult.errorRate * 100).toFixed(2)}%`} />
                  <MetricCard title="Cache Hit" value={`${(expandedResult.cacheHitRate * 100).toFixed(1)}%`} />
                  <MetricCard title="Avg TTFB" value={expandedResult.avgTtfbMs} unit="ms" />
                  <MetricCard title="Total Requests" value={expandedResult.totalRequests ?? "—"} />
                </div>
                {expandedResult.agentSummary && (
                  <div className="p-3 rounded text-sm mb-3" style={{ backgroundColor: "var(--background-hover)", color: "var(--text-secondary)" }}>
                    {expandedResult.agentSummary}
                  </div>
                )}
                {expandedResult.anomalies.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>Anomalies</h4>
                    {expandedResult.anomalies.map((a, i) => (
                      <div key={i} className="text-sm py-1" style={{ color: "var(--text-secondary)" }}>
                        • [{a.severity}] {a.type}: {a.description ?? ""}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <AgentChatPanel appName="Log Analyzer" />
    </div>
  );
}
