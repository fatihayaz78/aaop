"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import MetricCard from "@/components/ui/MetricCard";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import RiskBadge from "@/components/ui/RiskBadge";
import { AccordionItem } from "@/components/ui/Accordion";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost, apiDelete } from "@/lib/api";
import type { LogProject, FetchJob, AnalysisResult } from "@/types";

type Tab = "projects" | "analyzer" | "structure" | "anomaly" | "settings" | "results";

/* ── Revised 21 chart names (match backend) ── */
const CHART_TYPES = [
  "transfer_time_trend", "dns_latency_distribution", "turnaround_time_trend", "latency_correlation",
  "bandwidth_trend", "bytes_vs_clientbytes", "response_size_distribution",
  "status_code_distribution", "error_rate_trend", "error_code_breakdown",
  "cache_hit_ratio_trend", "cache_status_breakdown", "cache_vs_error",
  "geographic_distribution", "city_top20", "content_type_breakdown", "top_urls",
  "top_client_ips", "edge_server_load", "peak_hour_heatmap", "anomaly_timeline",
] as const;

const BAR_CHARTS = new Set([
  "dns_latency_distribution", "response_size_distribution", "status_code_distribution",
  "error_code_breakdown", "cache_status_breakdown", "geographic_distribution",
  "city_top20", "content_type_breakdown", "top_urls", "top_client_ips", "edge_server_load",
  "peak_hour_heatmap",
]);

/* ── BigQuery export categories ── */
const BQ_CATEGORIES: { name: string; fields: string[]; note?: string }[] = [
  { name: "Meta", fields: ["version", "cp_code"] },
  { name: "Timing", fields: ["transfer_time", "turnaround_time", "dns_lookup_time", "total_bytes_time"] },
  { name: "Traffic", fields: ["bytes", "client_bytes", "overhead_bytes"] },
  { name: "Content", fields: ["content_type", "request_method"] },
  { name: "Client", fields: ["user_agent", "client_country"], note: "client_ip excluded (PII)" },
  { name: "Network", fields: ["protocol", "tls_version"] },
  { name: "Response", fields: ["status_code", "custom_field"] },
  { name: "Cache", fields: ["cache_status", "cache_hit"] },
  { name: "Geo", fields: ["city", "region"] },
];

/* ── Settings types ── */
interface AwsSettings {
  aws_access_key_id: string;
  aws_secret_access_key: string;
  aws_region: string;
  s3_bucket: string;
  s3_prefix: string;
}

interface BqSettings {
  gcp_project_id: string;
  bq_dataset_id: string;
  gcp_service_account_json: string;
  bq_export_enabled: boolean;
}

interface BqExportJob {
  job_id: string;
  table_id: string;
  rows_exported: number;
  status: "queued" | "running" | "completed" | "failed";
  exported_at?: string;
  progress?: number;
  error?: string;
}

interface AppSettings {
  language: "en" | "tr";
  default_date_range: "7d" | "30d" | "custom";
  log_cache_retention: "7" | "14" | "30";
  auto_fetch_schedule: "disabled" | "6h" | "12h" | "daily";
  cp_code: string;
}

/* ── Log Structure types ── */
interface FieldAnalysis {
  field_name: string;
  description: string;
  sample_values: string[];
  null_count: number;
  unique_count: number;
  inferred_type: string;
  current_category: string | null;
}

interface StructureResult {
  fields: FieldAnalysis[];
  total_rows_sampled: number;
  files_scanned: number;
  error?: string;
}

const FIELD_CATEGORIES = ["meta", "timing", "traffic", "content", "client", "network", "response", "cache", "geo", "custom"] as const;

const TYPE_COLORS: Record<string, { bg: string; color: string }> = {
  timestamp: { bg: "rgba(59,130,246,0.15)", color: "#3b82f6" },
  integer: { bg: "rgba(34,197,94,0.15)", color: "#22c55e" },
  float: { bg: "rgba(234,179,8,0.15)", color: "#eab308" },
  string: { bg: "rgba(156,163,175,0.15)", color: "#9ca3af" },
  ip_hash: { bg: "rgba(239,68,68,0.15)", color: "#ef4444" },
  boolean: { bg: "rgba(168,85,247,0.15)", color: "#a855f7" },
};

export default function LogAnalyzer() {
  const [tab, setTab] = useState<Tab>("projects");

  /* ── Projects state ── */
  const [projects, setProjects] = useState<LogProject[]>([]);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectModule, setNewProjectModule] = useState("akamai");

  /* ── Log Analyzer tab state ── */
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [akamaiConfig, setAkamaiConfig] = useState({ s3_bucket: "ssport-datastream", s3_prefix: "logs/", schedule_cron: "0 */6 * * *" });
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [fetchJob, setFetchJob] = useState<FetchJob | null>(null);
  const [chartsData, setChartsData] = useState<Record<string, Record<string, unknown>[]>>({});

  /* ── Results state ── */
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [expandedResult, setExpandedResult] = useState<AnalysisResult | null>(null);
  const [jobHistory, setJobHistory] = useState<Record<string, unknown>[]>([]);

  /* ── App Settings state ── */
  const [appSettings, setAppSettings] = useState<AppSettings>({ language: "en", default_date_range: "7d", log_cache_retention: "7", auto_fetch_schedule: "disabled", cp_code: "" });

  /* ── Anomaly Rules state ── */
  const [anomalyRules, setAnomalyRules] = useState<Record<string, unknown>[]>([]);
  const [showNewRule, setShowNewRule] = useState(false);
  const [newRule, setNewRule] = useState({ name: "", field: "country", operator: "not_in", value: "", severity: "medium", description: "" });
  const [anomalyResults, setAnomalyResults] = useState<Record<string, unknown>[]>([]);
  const [anomalyLoading, setAnomalyLoading] = useState(false);

  /* ── Log Structure state ── */
  const [structStartDate, setStructStartDate] = useState("");
  const [structEndDate, setStructEndDate] = useState("");
  const [structSampleSize, setStructSampleSize] = useState(1000);
  const [structLoading, setStructLoading] = useState(false);
  const [structResult, setStructResult] = useState<StructureResult | null>(null);
  const [structError, setStructError] = useState("");
  const [fieldCategories, setFieldCategories] = useState<Record<string, string>>({});
  const [savedFields, setSavedFields] = useState<Set<string>>(new Set());

  /* ── AWS Settings state ── */
  const [awsSettings, setAwsSettings] = useState<AwsSettings>({ aws_access_key_id: "", aws_secret_access_key: "", aws_region: "eu-central-1", s3_bucket: "ssport-datastream", s3_prefix: "logs/" });
  const [bqSettings, setBqSettings] = useState<BqSettings>({ gcp_project_id: "", bq_dataset_id: "", gcp_service_account_json: "", bq_export_enabled: false });
  const [showAwsKey, setShowAwsKey] = useState(false);
  const [showAwsSecret, setShowAwsSecret] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState("");
  const [s3TestResult, setS3TestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [bqTestResult, setBqTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [bqSettingsMsg, setBqSettingsMsg] = useState("");
  const [appSettingsMsg, setAppSettingsMsg] = useState("");

  /* ── BigQuery Export state (now inside Settings) ── */
  const [bqCategories, setBqCategories] = useState<Record<string, boolean>>(() => Object.fromEntries(BQ_CATEGORIES.map((c) => [c.name, true])));
  const [bqTableId, setBqTableId] = useState("");
  const [bqSelectedJob, setBqSelectedJob] = useState("");
  const [bqRecentJobs, setBqRecentJobs] = useState<{ jobId: string; label: string }[]>([]);
  const [bqExportJob, setBqExportJob] = useState<BqExportJob | null>(null);
  const [bqHistory, setBqHistory] = useState<BqExportJob[]>([]);
  const bqPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* ── Data loading ── */
  const loadProjects = useCallback(async () => {
    try { setProjects(await apiGet<LogProject[]>("/log-analyzer/projects?tenant_id=s_sport_plus")); } catch { /* backend offline */ }
  }, []);

  const loadResults = useCallback(async () => {
    try { setResults(await apiGet<AnalysisResult[]>("/log-analyzer/results?tenant_id=s_sport_plus&limit=20")); } catch { /* backend offline */ }
  }, []);

  const loadSettings = useCallback(async () => {
    try {
      const s = await apiGet<AwsSettings & BqSettings & { cp_code?: string }>("/log-analyzer/settings?tenant_id=s_sport_plus");
      setAwsSettings({ aws_access_key_id: s.aws_access_key_id ?? "", aws_secret_access_key: s.aws_secret_access_key ?? "", aws_region: s.aws_region ?? "eu-central-1", s3_bucket: s.s3_bucket ?? "ssport-datastream", s3_prefix: s.s3_prefix ?? "logs/" });
      setBqSettings({ gcp_project_id: s.gcp_project_id ?? "", bq_dataset_id: s.bq_dataset_id ?? "", gcp_service_account_json: s.gcp_service_account_json ?? "", bq_export_enabled: s.bq_export_enabled ?? false });
      setAppSettings((prev) => ({ ...prev, cp_code: s.cp_code ?? "" }));
    } catch { /* backend offline */ }
  }, []);

  const loadBqHistory = useCallback(async () => {
    try { setBqHistory(await apiGet<BqExportJob[]>("/log-analyzer/bigquery/jobs?tenant_id=s_sport_plus&limit=10")); } catch { /* */ }
  }, []);

  const loadBqRecentJobs = useCallback(async () => {
    try {
      const jobs = await apiGet<{ jobId: string; createdAt: string }[]>("/log-analyzer/akamai/jobs?tenant_id=s_sport_plus&limit=10");
      setBqRecentJobs(jobs.map((j) => ({ jobId: j.jobId, label: `${j.jobId} (${j.createdAt})` })));
    } catch { /* */ }
  }, []);

  useEffect(() => {
    loadProjects();
    loadResults();
  }, [loadProjects, loadResults]);

  useEffect(() => {
    if (tab === "settings") { loadSettings(); loadBqHistory(); loadBqRecentJobs(); }
    if (tab === "structure") {
      // Load saved mappings on tab switch
      (async () => {
        try {
          const mappings = await apiGet<{ field_name: string; category: string }[]>("/log-analyzer/structure/mappings?tenant_id=s_sport_plus");
          const cats: Record<string, string> = {};
          const saved = new Set<string>();
          for (const m of mappings) { cats[m.field_name] = m.category; saved.add(m.field_name); }
          setFieldCategories((prev) => ({ ...cats, ...prev }));
          setSavedFields((prev) => new Set([...Array.from(prev), ...Array.from(saved)]));
        } catch { /* */ }
      })();
    }
    if (tab === "anomaly") {
      (async () => {
        try { setAnomalyRules(await apiGet<Record<string, unknown>[]>("/log-analyzer/anomaly-rules?tenant_id=s_sport_plus")); } catch { /* */ }
      })();
    }
    if (tab === "results") {
      (async () => {
        try { setJobHistory(await apiGet<Record<string, unknown>[]>("/log-analyzer/akamai/jobs?tenant_id=s_sport_plus")); } catch { /* */ }
      })();
    }
  }, [tab, loadSettings, loadBqHistory, loadBqRecentJobs]);

  const viewJobCharts = (jobId: string) => {
    setTab("analyzer");
    loadCharts(jobId);
  };

  /* ── Projects ── */
  const createProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      await apiPost("/log-analyzer/projects", { tenant_id: "s_sport_plus", name: newProjectName, sub_module: newProjectModule });
      setNewProjectName("");
      setShowNewProject(false);
      loadProjects();
    } catch { /* error */ }
  };

  const deleteProject = async (id: string) => {
    if (!confirm("Delete this project?")) return;
    try { await apiDelete(`/log-analyzer/projects/${id}`); loadProjects(); } catch { /* error */ }
  };

  /* ── Akamai ── */
  const [configMsg, setConfigMsg] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [fetchMode, setFetchMode] = useState<"sampled" | "full">("sampled");

  const configureAkamai = async () => {
    try {
      await apiPost("/log-analyzer/akamai/configure", { project_id: selectedProjectId || null, ...akamaiConfig, enabled: true });
      setConfigMsg("Config saved.");
      setTimeout(() => setConfigMsg(""), 3000);
    } catch { setConfigMsg("Failed to save config."); }
  };

  const fetchLogsForRange = async () => {
    if (!startDate || !endDate) return;
    setFetchJob(null);
    try {
      const res = await apiPost<FetchJob & { error?: string }>("/log-analyzer/akamai/fetch-range", { start_date: startDate, end_date: endDate, cache_mode: forceRefresh ? "force_refresh" : "auto", fetch_mode: fetchMode });
      if (res.error) {
        setFetchJob({ jobId: "", job_id: "", status: "failed", error: res.error, progress: 0 });
        return;
      }
      const jobId = res.job_id || res.jobId;
      setFetchJob({ ...res, jobId: jobId });
      pollJob(jobId);
    } catch { setFetchJob({ jobId: "", status: "failed", error: "Failed to connect to backend.", progress: 0 }); }
  };

  const pollJob = (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const raw = await apiGet<Record<string, unknown>>(`/log-analyzer/akamai/jobs/${jobId}`);
        const job: FetchJob = {
          jobId: (raw.job_id || raw.jobId || jobId) as string,
          status: raw.status as FetchJob["status"],
          progress: raw.progress as number | undefined,
          total_files: raw.total_files as number | undefined,
          files_downloaded: raw.files_downloaded as number | undefined,
          rows_parsed: raw.rows_parsed as number | undefined,
          cache_hits: raw.cache_hits as number | undefined,
          cache_misses: raw.cache_misses as number | undefined,
          message: raw.message as string | undefined,
          error: raw.error as string | undefined,
        };
        setFetchJob(job);
        if (job.status === "completed" || job.status === "failed" || job.status === "cancelled") {
          clearInterval(interval);
          if (job.status === "completed") loadCharts(jobId);
        }
      } catch { clearInterval(interval); }
    }, 2000);
  };

  /* ── Analysis state ── */
  const [analysisSummary, setAnalysisSummary] = useState<Record<string, number>>({});

  const loadCharts = async (jobId: string) => {
    try {
      const res = await apiGet<{ summary: Record<string, number>; charts: Record<string, Record<string, unknown>[]>; error?: string }>(`/log-analyzer/akamai/analysis/${jobId}`);
      if (res.error) return;
      setAnalysisSummary(res.summary ?? {});
      setChartsData(res.charts ?? {});
    } catch { /* backend offline */ }
  };

  const downloadReport = async () => {
    try { await apiPost("/log-analyzer/akamai/report", { tenant_id: "s_sport_plus" }); } catch { /* error */ }
  };

  /* ── Settings ── */
  const saveAppSettings = async () => {
    try {
      await apiPost("/log-analyzer/settings", { cp_code: appSettings.cp_code });
      setAppSettingsMsg("Settings saved.");
      setTimeout(() => setAppSettingsMsg(""), 3000);
    } catch { setAppSettingsMsg("Failed to save settings."); }
  };

  const saveAwsSettings = async () => {
    try {
      await apiPost("/log-analyzer/settings", {
        aws_access_key_id: awsSettings.aws_access_key_id,
        aws_secret_access_key: awsSettings.aws_secret_access_key,
        s3_bucket: awsSettings.s3_bucket,
        aws_region: awsSettings.aws_region,
      });
      setSettingsMsg("AWS settings saved.");
      setS3TestResult(null);
      setTimeout(() => setSettingsMsg(""), 3000);
    } catch { setSettingsMsg("Failed to save AWS settings."); }
  };

  const testS3Connection = async () => {
    setS3TestResult(null);
    try {
      const res = await apiGet<{ success: boolean; message: string }>("/log-analyzer/settings/test-connection?type=s3&tenant_id=s_sport_plus");
      setS3TestResult(res);
    } catch { setS3TestResult({ success: false, message: "Connection test request failed." }); }
  };

  const testBqConnection = async () => {
    setBqTestResult(null);
    try {
      const res = await apiGet<{ success: boolean; message: string }>("/log-analyzer/settings/test-connection?type=bq&tenant_id=s_sport_plus");
      setBqTestResult(res);
    } catch { setBqTestResult({ success: false, message: "Connection test request failed." }); }
  };

  const clearCredentials = async () => {
    if (!confirm("This is a HIGH RISK action. Are you sure you want to clear all credentials?")) return;
    try {
      await apiDelete("/log-analyzer/settings/credentials?tenant_id=s_sport_plus");
      setAwsSettings({ aws_access_key_id: "", aws_secret_access_key: "", aws_region: "eu-central-1", s3_bucket: "ssport-datastream", s3_prefix: "logs/" });
      setSettingsMsg("Credentials cleared.");
      setS3TestResult(null);
      setTimeout(() => setSettingsMsg(""), 3000);
    } catch { setSettingsMsg("Failed to clear credentials."); }
  };

  /* ── Log Structure Analysis ── */
  const analyzeStructure = async () => {
    if (!structStartDate || !structEndDate) return;
    setStructLoading(true);
    setStructError("");
    setStructResult(null);
    try {
      const res = await apiPost<StructureResult>("/log-analyzer/structure/analyze", {
        start_date: structStartDate,
        end_date: structEndDate,
        sample_size: structSampleSize,
      });
      if (res.error) {
        setStructError(res.error);
      } else {
        setStructResult(res);
        // Pre-fill categories from API response (saved or DS2 default)
        const cats: Record<string, string> = { ...fieldCategories };
        for (const f of res.fields) {
          if (f.current_category && !cats[f.field_name]) {
            cats[f.field_name] = f.current_category;
          }
        }
        setFieldCategories(cats);
      }
    } catch { setStructError("Failed to connect to backend."); }
    setStructLoading(false);
  };

  const saveFieldMapping = async (fieldName: string) => {
    const category = fieldCategories[fieldName];
    if (!category) return;
    try {
      await apiPost("/log-analyzer/structure/mappings", { field_name: fieldName, category });
      setSavedFields((prev) => new Set([...Array.from(prev), fieldName]));
    } catch { /* error */ }
  };

  const exportMappings = () => {
    if (!structResult) return;
    const mappings = structResult.fields
      .filter((f) => fieldCategories[f.field_name])
      .map((f) => ({ field_name: f.field_name, category: fieldCategories[f.field_name] }));
    const blob = new Blob([JSON.stringify(mappings, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "field_mappings.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const saveBqSettings = async () => {
    try {
      await apiPost("/log-analyzer/settings", {
        gcp_project_id: bqSettings.gcp_project_id,
        gcp_dataset_id: bqSettings.bq_dataset_id,
        gcp_credentials_json: bqSettings.gcp_service_account_json,
      });
      setBqSettingsMsg("GCP settings saved.");
      setBqTestResult(null);
      setTimeout(() => setBqSettingsMsg(""), 3000);
    } catch { setBqSettingsMsg("Failed to save GCP settings."); }
  };

  /* ── BigQuery Export ── */
  const startBqExport = async () => {
    if (!bqSelectedJob) return;
    const selectedCategories = BQ_CATEGORIES.filter((c) => bqCategories[c.name]).map((c) => c.name.toLowerCase());
    try {
      const job = await apiPost<BqExportJob>(
        "/log-analyzer/bigquery/export",
        { job_id: bqSelectedJob, categories: selectedCategories, bq_table_id: bqTableId || `akamai_logs_${bqSelectedJob}` },
      );
      setBqExportJob(job);
      pollBqExport(job.job_id);
    } catch { /* error */ }
  };

  const pollBqExport = (jobId: string) => {
    if (bqPollRef.current) clearInterval(bqPollRef.current);
    bqPollRef.current = setInterval(async () => {
      try {
        const job = await apiGet<BqExportJob>(`/log-analyzer/bigquery/jobs/${jobId}`);
        setBqExportJob(job);
        if (job.status === "completed" || job.status === "failed") {
          if (bqPollRef.current) clearInterval(bqPollRef.current);
          bqPollRef.current = null;
          loadBqHistory();
        }
      } catch {
        if (bqPollRef.current) clearInterval(bqPollRef.current);
        bqPollRef.current = null;
      }
    }, 3000);
  };

  useEffect(() => { return () => { if (bqPollRef.current) clearInterval(bqPollRef.current); }; }, []);

  const bqExportProgress = bqExportJob?.status === "completed" ? 100 : bqExportJob?.status === "running" ? (bqExportJob.progress ?? 50) : bqExportJob?.status === "queued" ? 10 : 0;

  /* ── Shared ── */
  const jobProgress = fetchJob?.progress ?? (
    fetchJob?.status === "completed" ? 100 :
    fetchJob?.status === "parsing" ? 70 :
    fetchJob?.status === "downloading" ? 40 :
    fetchJob?.status === "queued" ? 10 :
    fetchJob?.status === "cancelled" ? 0 : 0
  );
  const isJobRunning = fetchJob?.status === "queued" || fetchJob?.status === "downloading" || fetchJob?.status === "parsing";

  const cancelJob = async () => {
    const jid = fetchJob?.jobId || fetchJob?.job_id;
    if (!jid) return;
    try {
      await apiPost(`/log-analyzer/akamai/jobs/${jid}/cancel`, {});
    } catch { /* */ }
  };

  const TABS: { key: Tab; label: string }[] = [
    { key: "projects", label: "Projects" },
    { key: "analyzer", label: "Log Analyzer" },
    { key: "structure", label: "Log Structure" },
    { key: "anomaly", label: "Anomaly Rules" },
    { key: "settings", label: "Settings" },
    { key: "results", label: "Analysis Results" },
  ];

  /* ── Password field helper ── */
  const PasswordField = ({ label, value, onChange, show, onToggle }: { label: string; value: string; onChange: (v: string) => void; show: boolean; onToggle: () => void }) => (
    <div>
      <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>{label}</label>
      <div className="flex gap-1">
        <input type={show ? "text" : "password"} value={value} onChange={(e) => onChange(e.target.value)}
          className="flex-1 text-sm px-3 py-2 rounded border outline-none font-mono"
          style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
        <button type="button" onClick={onToggle} className="px-2 py-1 rounded border text-xs"
          style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
          {show ? "Hide" : "Show"}
        </button>
      </div>
    </div>
  );

  /* ── Connection test badge ── */
  const TestResultBadge = ({ result }: { result: { success: boolean; message: string } | null }) => {
    if (!result) return null;
    return (
      <span className="inline-flex items-center text-xs px-2 py-1 rounded ml-2"
        style={{
          backgroundColor: result.success ? "var(--risk-low-bg)" : "var(--risk-high-bg)",
          color: result.success ? "var(--risk-low)" : "var(--risk-high)",
        }}>
        {result.success ? "Connected" : "Failed"}: {result.message}
      </span>
    );
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Log Analyzer</h2>

      {/* ── Tab bar ── */}
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ══════════ Tab 1: Projects ══════════ */}
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

      {/* ══════════ Tab 2: Log Analyzer (renamed from Akamai Analyzer) ══════════ */}
      {tab === "analyzer" && (
        <div>
          {/* Project selector */}
          <div className="rounded-lg border p-4 mb-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <label className="text-xs font-medium block mb-2" style={{ color: "var(--text-secondary)" }}>Active Project</label>
            {projects.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                No projects found.{" "}
                <button onClick={() => setTab("projects")} className="underline" style={{ color: "var(--brand-primary)" }}>
                  Create a project first
                </button>
              </p>
            ) : (
              <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)}
                className="w-full md:w-80 text-sm px-3 py-2 rounded border outline-none"
                style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                <option value="">Select a project...</option>
                {projects.map((p) => (
                  <option key={p.projectId} value={p.projectId}>{p.name} ({p.subModule})</option>
                ))}
              </select>
            )}
          </div>

          {/* Akamai DataStream 2 sub-section */}
          <div className="rounded-lg border p-4 mb-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Akamai DataStream 2</h3>
              <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>Source</span>
            </div>

            {/* Config form */}
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

            {/* Date range inputs */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Start Date</label>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                  className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                  style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>End Date</label>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                  className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                  style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              </div>
              <div className="flex flex-col items-start gap-2 justify-end">
                <button onClick={fetchLogsForRange} disabled={!startDate || !endDate || isJobRunning}
                  className="px-4 py-1.5 rounded text-sm font-medium disabled:opacity-50"
                  style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
                  Fetch Logs
                </button>
                <div className="flex items-center gap-3">
                  <select value={fetchMode} onChange={(e) => setFetchMode(e.target.value as "sampled" | "full")}
                    className="text-xs px-2 py-1 rounded border outline-none"
                    style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                    <option value="sampled">Sampled (fast)</option>
                    <option value="full">Full (all data)</option>
                  </select>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input type="checkbox" checked={forceRefresh} onChange={(e) => setForceRefresh(e.target.checked)} />
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>Ignore cache</span>
                  </label>
                </div>
              </div>
            </div>
            {fetchMode === "full" && (
              <div className="rounded p-2 text-xs mt-2" style={{ backgroundColor: "var(--risk-medium-bg)", color: "var(--risk-medium)" }}>
                Full mode fetches all available files. This may take a long time for large date ranges.
              </div>
            )}

            <div className="flex gap-2 items-center">
              <button onClick={configureAkamai} className="px-4 py-1.5 rounded text-sm font-medium border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Save Config</button>
              <button onClick={downloadReport} className="px-4 py-1.5 rounded text-sm font-medium border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Download Report (DOCX)</button>
              {configMsg && <span className="text-xs" style={{ color: configMsg.includes("Failed") ? "var(--risk-high)" : "var(--risk-low)" }}>{configMsg}</span>}
            </div>
          </div>

          {/* Job progress */}
          {fetchJob && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                  {fetchJob.jobId ? `Job: ${fetchJob.jobId.slice(0, 8)}...` : "Job"}
                  {fetchJob.files_downloaded != null && fetchJob.total_files ? ` — ${fetchJob.files_downloaded}/${fetchJob.total_files} files` : ""}
                  {fetchJob.rows_parsed ? ` — ${fetchJob.rows_parsed.toLocaleString()} rows` : ""}
                  {fetchJob.cache_hits ? ` (${fetchJob.cache_hits} cached)` : ""}
                </span>
                <div className="flex items-center gap-2">
                  {isJobRunning && (
                    <button onClick={cancelJob} className="text-xs px-2 py-0.5 rounded border"
                      style={{ borderColor: "var(--risk-high)", color: "var(--risk-high)" }}>
                      Stop
                    </button>
                  )}
                  <span className="text-xs" style={{
                    color: fetchJob.status === "completed" ? "var(--risk-low)" :
                           fetchJob.status === "failed" ? "var(--risk-high)" :
                           fetchJob.status === "cancelled" ? "var(--risk-medium)" :
                           "var(--brand-primary)"
                  }}>
                    {fetchJob.status}
                  </span>
                </div>
              </div>
              <div className="w-full h-2 rounded-full" style={{ backgroundColor: "var(--border)" }}>
                <div className="h-2 rounded-full transition-all" style={{
                  width: `${jobProgress}%`,
                  backgroundColor: fetchJob.status === "failed" ? "var(--risk-high)" :
                                   fetchJob.status === "cancelled" ? "var(--risk-medium)" :
                                   "var(--brand-primary)"
                }} />
              </div>
              {fetchJob.message && (
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{fetchJob.message}</p>
              )}
              {fetchJob.status === "failed" && fetchJob.error && (
                <p className="text-xs mt-1" style={{ color: "var(--risk-high)" }}>{fetchJob.error}</p>
              )}
            </div>
          )}

          {/* Analysis summary + charts */}
          {Object.keys(chartsData).length > 0 && (
            <div className="space-y-4">
              {/* 6 Summary metric cards */}
              {analysisSummary && Object.keys(analysisSummary).length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                  <MetricCard title="Total Rows" value={(analysisSummary.total_rows ?? 0).toLocaleString()} />
                  <MetricCard title="Total GB" value={analysisSummary.total_gb ?? 0} unit="GB" />
                  <MetricCard title="Avg Latency" value={analysisSummary.avg_latency_ms ?? 0} unit="ms" />
                  <MetricCard title="Error Rate" value={`${analysisSummary.error_rate_pct ?? 0}%`} />
                  <MetricCard title="Cache Hit" value={`${analysisSummary.cache_hit_pct ?? 0}%`} />
                  <MetricCard title="Countries" value={analysisSummary.unique_countries ?? 0} />
                </div>
              )}

              {/* 10 Charts grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {([
                  { key: "status_code_distribution", title: "Status Code Distribution", x: "status", y: "count", type: "bar" as const },
                  { key: "cache_hit_ratio", title: "Cache Hit Ratio", x: "label", y: "count", type: "bar" as const },
                  { key: "bandwidth_by_hour", title: "Bandwidth by Hour (MB)", x: "hour", y: "mb", type: "line" as const },
                  { key: "top_error_paths", title: "Top Error Paths", x: "path", y: "count", type: "bar" as const },
                  { key: "latency_percentiles", title: "Latency Percentiles (ms)", x: "percentile", y: "ms", type: "bar" as const },
                  { key: "geo_distribution", title: "Geographic Distribution", x: "country", y: "count", type: "bar" as const },
                  { key: "content_type_breakdown", title: "Content Type Breakdown", x: "type", y: "count", type: "bar" as const },
                  { key: "cache_status_breakdown", title: "Cache Status Breakdown", x: "status", y: "count", type: "bar" as const },
                  { key: "error_rate_trend", title: "Error Rate Trend (%)", x: "hour", y: "error_rate", type: "line" as const },
                  { key: "bytes_vs_client", title: "Server vs Client (MB)", x: "hour", y: "server_mb", type: "line" as const },
                  { key: "top_client_ips", title: "Top 10 Client IPs (MB)", x: "ip", y: "mb", type: "bar" as const },
                  { key: "request_volume_by_hour", title: "Request Volume by Hour", x: "hour", y: "requests", type: "bar" as const },
                  { key: "anomaly_timeline", title: "Anomaly Timeline (Latency)", x: "hour", y: "avg_ms", type: "line" as const },
                ] as const).map((chart) => {
                  const data = chartsData[chart.key] ?? [];
                  if (!data.length) return null;
                  return (
                    <div key={chart.key} className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                      <RechartsWrapper
                        data={data as Record<string, unknown>[]}
                        xKey={chart.x}
                        yKey={chart.y}
                        title={chart.title}
                        height={180}
                        type={chart.type}
                      />
                      <details className="mt-2">
                        <summary className="text-xs cursor-pointer select-none" style={{ color: "var(--text-muted)" }}>Data Table</summary>
                        <div className="mt-1 max-h-40 overflow-y-auto">
                          <table className="w-full text-xs" style={{ color: "var(--text-secondary)" }}>
                            <thead>
                              <tr>
                                {data[0] && Object.keys(data[0]).map((k) => (
                                  <th key={k} className="text-left px-1 py-0.5 font-medium border-b" style={{ borderColor: "var(--border)" }}>{k}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {data.slice(0, 10).map((row, i) => (
                                <tr key={i}>
                                  {Object.values(row).map((v, j) => (
                                    <td key={j} className="px-1 py-0.5 border-b" style={{ borderColor: "var(--border)" }}>{String(v ?? "")}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </details>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {Object.keys(chartsData).length === 0 && !fetchJob && (
            <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>Fetch logs to see analysis charts.</p>
            </div>
          )}
        </div>
      )}

      {/* ══════════ Tab 3: Log Structure ══════════ */}
      {tab === "structure" && (
        <div className="space-y-6">
          {/* Section 1: Date Range Selector */}
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Analyze Log Structure</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Start Date</label>
                <input type="date" value={structStartDate} onChange={(e) => setStructStartDate(e.target.value)}
                  className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                  style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>End Date</label>
                <input type="date" value={structEndDate} onChange={(e) => setStructEndDate(e.target.value)}
                  className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                  style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Sample Size (max 5000)</label>
                <input type="number" value={structSampleSize} min={100} max={5000}
                  onChange={(e) => setStructSampleSize(Math.min(5000, Math.max(100, Number(e.target.value))))}
                  className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                  style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
              </div>
              <div className="flex items-end">
                <button onClick={analyzeStructure} disabled={!structStartDate || !structEndDate || structLoading}
                  className="px-4 py-1.5 rounded text-sm font-medium disabled:opacity-50"
                  style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
                  {structLoading ? "Scanning S3 logs..." : "Analyze Log Structure"}
                </button>
              </div>
            </div>

            {structLoading && (
              <div className="flex items-center gap-2 py-2">
                <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: "var(--border)", borderTopColor: "var(--brand-primary)" }} />
                <span className="text-sm" style={{ color: "var(--text-muted)" }}>Scanning S3 logs...</span>
              </div>
            )}

            {structError && (
              <div className="rounded p-3 text-sm" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>
                {structError}
              </div>
            )}
          </div>

          {/* Section 2: Field Analysis Table */}
          {structResult && structResult.fields.length > 0 && (
            <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <div className="p-4 border-b" style={{ borderColor: "var(--border)" }}>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  {structResult.fields.length} fields detected across {structResult.total_rows_sampled.toLocaleString()} rows sampled from {structResult.files_scanned} files
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      {["Field Name", "Type", "Description", "Sample Values", "Null %", "Unique Count", "Category", "Action"].map((h) => (
                        <th key={h} className="text-left px-4 py-2 text-xs font-medium" style={{ color: "var(--text-muted)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {structResult.fields.map((f) => {
                      const totalRows = structResult.total_rows_sampled;
                      const nullPct = totalRows > 0 ? ((f.null_count / totalRows) * 100) : 0;
                      const typeStyle = TYPE_COLORS[f.inferred_type] || TYPE_COLORS.string;
                      return (
                        <tr key={f.field_name} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: "var(--text-primary)" }}>{f.field_name}</td>
                          <td className="px-4 py-2">
                            <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: typeStyle.bg, color: typeStyle.color }}>
                              {f.inferred_type}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <span className="text-xs italic" style={{ color: "var(--text-muted)" }}>{f.description || "—"}</span>
                          </td>
                          <td className="px-4 py-2">
                            <div className="flex flex-wrap gap-1">
                              {f.sample_values.length > 0 ? f.sample_values.map((v, i) => (
                                <span key={i} className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ backgroundColor: "var(--background)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                                  {v.length > 20 ? v.slice(0, 20) + "..." : v}
                                </span>
                              )) : <span className="text-xs" style={{ color: "var(--text-muted)" }}>—</span>}
                            </div>
                          </td>
                          <td className="px-4 py-2">
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1.5 rounded-full" style={{ backgroundColor: "var(--border)" }}>
                                <div className="h-1.5 rounded-full" style={{ width: `${Math.min(nullPct, 100)}%`, backgroundColor: nullPct > 50 ? "var(--risk-high)" : nullPct > 10 ? "var(--risk-medium)" : "var(--risk-low)" }} />
                              </div>
                              <span className="text-xs" style={{ color: "var(--text-muted)" }}>{nullPct.toFixed(1)}%</span>
                            </div>
                          </td>
                          <td className="px-4 py-2 text-xs" style={{ color: "var(--text-secondary)" }}>{f.unique_count.toLocaleString()}</td>
                          <td className="px-4 py-2">
                            <select
                              value={fieldCategories[f.field_name] ?? ""}
                              onChange={(e) => {
                                setFieldCategories({ ...fieldCategories, [f.field_name]: e.target.value });
                                setSavedFields((prev) => { const n = new Set(prev); n.delete(f.field_name); return n; });
                              }}
                              className="text-xs px-2 py-1 rounded border outline-none"
                              style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                              <option value="">--</option>
                              {FIELD_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                            </select>
                          </td>
                          <td className="px-4 py-2">
                            {savedFields.has(f.field_name) ? (
                              <span className="text-xs" style={{ color: "var(--risk-low)" }}>Saved</span>
                            ) : fieldCategories[f.field_name] ? (
                              <button onClick={() => saveFieldMapping(f.field_name)}
                                className="text-xs px-2 py-1 rounded border"
                                style={{ borderColor: "var(--brand-primary)", color: "var(--brand-primary)" }}>
                                Save
                              </button>
                            ) : (
                              <span className="text-xs" style={{ color: "var(--text-muted)" }}>--</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Section 3: Category Summary */}
          {structResult && savedFields.size > 0 && (() => {
            const categoryMap: Record<string, string[]> = {};
            for (const [field, cat] of Object.entries(fieldCategories)) {
              if (cat && savedFields.has(field)) {
                if (!categoryMap[cat]) categoryMap[cat] = [];
                categoryMap[cat].push(field);
              }
            }
            const cats = Object.entries(categoryMap).sort(([a], [b]) => a.localeCompare(b));
            if (cats.length === 0) return null;
            return (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Category Summary</h3>
                  <button onClick={exportMappings} className="px-3 py-1 rounded text-xs font-medium border"
                    style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
                    Export Mappings
                  </button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {cats.map(([cat, fields]) => (
                    <div key={cat} className="rounded-lg border p-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                      <h4 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--brand-primary)" }}>{cat}</h4>
                      <div className="flex flex-wrap gap-1">
                        {fields.map((f) => (
                          <span key={f} className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ backgroundColor: "var(--background)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                            {f}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* ══════════ Tab: Anomaly Rules ══════════ */}
      {tab === "anomaly" && (
        <div className="space-y-6">
          {/* Section 1: Rules list */}
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Anomaly Rules</h3>
              <button onClick={() => setShowNewRule(!showNewRule)} className="px-3 py-1 rounded text-xs font-medium"
                style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
                {showNewRule ? "Cancel" : "+ Add Rule"}
              </button>
            </div>

            {showNewRule && (
              <div className="p-4 border-b space-y-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--background)" }}>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Rule Name</label>
                    <input type="text" value={newRule.name} onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                      className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                      style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Field</label>
                    <select value={newRule.field} onChange={(e) => setNewRule({ ...newRule, field: e.target.value })}
                      className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                      style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      {["version","cp_code","req_time_sec","bytes","client_bytes","content_type","response_body_size","user_agent","hostname","req_path","status_code","client_ip","req_range","cache_status","dns_lookup_time_ms","transfer_time_ms","turn_around_time_ms","error_code","cache_hit","edge_ip","country","city"].map((f) => (
                        <option key={f} value={f}>{f}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Operator</label>
                    <select value={newRule.operator} onChange={(e) => setNewRule({ ...newRule, operator: e.target.value })}
                      className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                      style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      {[["not_in","not in"],["gt",">"],["lt","<"],["eq","="],["contains","contains"]].map(([v,l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Value <span className="text-xs" style={{ color: "var(--text-muted)" }}>(for not_in: comma-separated)</span></label>
                    <input type="text" value={newRule.value} onChange={(e) => setNewRule({ ...newRule, value: e.target.value })}
                      className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                      style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}
                      placeholder="TR,DE" />
                  </div>
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Severity</label>
                    <select value={newRule.severity} onChange={(e) => setNewRule({ ...newRule, severity: e.target.value })}
                      className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                      style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Description</label>
                    <input type="text" value={newRule.description} onChange={(e) => setNewRule({ ...newRule, description: e.target.value })}
                      className="w-full text-sm px-3 py-1.5 rounded border outline-none"
                      style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                  </div>
                </div>
                <button onClick={async () => {
                  if (!newRule.name || !newRule.value) return;
                  const val = newRule.operator === "not_in" ? JSON.stringify(newRule.value.split(",").map((s: string) => s.trim())) : newRule.value;
                  try {
                    await apiPost("/log-analyzer/anomaly-rules", { ...newRule, value: val });
                    setShowNewRule(false);
                    setNewRule({ name: "", field: "country", operator: "not_in", value: "", severity: "medium", description: "" });
                    setAnomalyRules(await apiGet("/log-analyzer/anomaly-rules?tenant_id=s_sport_plus"));
                  } catch { /* */ }
                }} className="px-4 py-1.5 rounded text-sm font-medium"
                  style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Save Rule</button>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Name", "Field", "Condition", "Severity", "Active", "Delete"].map((h) => (
                      <th key={h} className="text-left px-4 py-2 text-xs font-medium" style={{ color: "var(--text-muted)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {anomalyRules.map((r) => (
                    <tr key={String(r.id)} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td className="px-4 py-2 text-xs" style={{ color: "var(--text-primary)" }}>{String(r.name)}</td>
                      <td className="px-4 py-2 text-xs font-mono" style={{ color: "var(--text-secondary)" }}>{String(r.field)}</td>
                      <td className="px-4 py-2 text-xs" style={{ color: "var(--text-secondary)" }}>{String(r.operator)} {String(r.value).slice(0, 30)}</td>
                      <td className="px-4 py-2">
                        <span className="text-xs px-2 py-0.5 rounded" style={{
                          backgroundColor: r.severity === "high" ? "var(--risk-high-bg)" : r.severity === "medium" ? "var(--risk-medium-bg)" : "var(--risk-low-bg)",
                          color: r.severity === "high" ? "var(--risk-high)" : r.severity === "medium" ? "var(--risk-medium)" : "var(--risk-low)",
                        }}>{String(r.severity)}</span>
                      </td>
                      <td className="px-4 py-2 text-xs" style={{ color: r.is_active ? "var(--risk-low)" : "var(--text-muted)" }}>{r.is_active ? "Yes" : "No"}</td>
                      <td className="px-4 py-2">
                        <button onClick={async () => {
                          try {
                            await apiDelete(`/log-analyzer/anomaly-rules/${r.id}`);
                            setAnomalyRules(await apiGet("/log-analyzer/anomaly-rules?tenant_id=s_sport_plus"));
                          } catch { /* */ }
                        }} className="text-xs" style={{ color: "var(--risk-high)" }}>Delete</button>
                      </td>
                    </tr>
                  ))}
                  {anomalyRules.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-6 text-center text-sm" style={{ color: "var(--text-muted)" }}>No rules configured.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 2: Evaluate */}
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="flex items-center gap-3 mb-4">
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Anomaly Evaluation</h3>
              <button onClick={async () => {
                const lastJob = fetchJob?.jobId || fetchJob?.job_id;
                if (!lastJob) return;
                setAnomalyLoading(true);
                try {
                  setAnomalyResults(await apiPost<Record<string, unknown>[]>(`/log-analyzer/anomaly-rules/evaluate?job_id=${lastJob}`, {}));
                } catch { /* */ }
                setAnomalyLoading(false);
              }} disabled={anomalyLoading || !fetchJob?.jobId}
                className="px-3 py-1 rounded text-xs font-medium disabled:opacity-50"
                style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
                {anomalyLoading ? "Evaluating..." : "Evaluate Against Last Job"}
              </button>
            </div>

            {anomalyResults.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      {["Rule", "Severity", "Affected Rows", "% of Total", "Sample Values"].map((h) => (
                        <th key={h} className="text-left px-4 py-2 text-xs font-medium" style={{ color: "var(--text-muted)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {anomalyResults.map((r, i) => (
                      <tr key={i} style={{
                        borderBottom: "1px solid var(--border)",
                        backgroundColor: r.severity === "high" && Number(r.affected_rows) > 0 ? "rgba(239,68,68,0.05)" :
                                        r.severity === "medium" && Number(r.affected_rows) > 0 ? "rgba(234,179,8,0.05)" : "transparent",
                      }}>
                        <td className="px-4 py-2 text-xs" style={{ color: "var(--text-primary)" }}>{String(r.rule_name ?? r.error ?? "—")}</td>
                        <td className="px-4 py-2">
                          <span className="text-xs px-2 py-0.5 rounded" style={{
                            backgroundColor: r.severity === "high" ? "var(--risk-high-bg)" : r.severity === "medium" ? "var(--risk-medium-bg)" : "var(--risk-low-bg)",
                            color: r.severity === "high" ? "var(--risk-high)" : r.severity === "medium" ? "var(--risk-medium)" : "var(--risk-low)",
                          }}>{String(r.severity ?? "—")}</span>
                        </td>
                        <td className="px-4 py-2 text-xs" style={{ color: "var(--text-primary)" }}>{Number(r.affected_rows ?? 0).toLocaleString()}</td>
                        <td className="px-4 py-2 text-xs" style={{ color: "var(--text-secondary)" }}>{String(r.pct_of_total ?? 0)}%</td>
                        <td className="px-4 py-2">
                          <div className="flex flex-wrap gap-1">
                            {(r.sample_values as string[] ?? []).slice(0, 5).map((v: string, j: number) => (
                              <span key={j} className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ backgroundColor: "var(--background)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                                {String(v).slice(0, 20)}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══════════ Tab 4: Analysis Results ══════════ */}
      {tab === "results" && (
        <div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="p-4 border-b" style={{ borderColor: "var(--border)" }}>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Fetch Job History</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Job ID", "Date Range", "Files", "Rows", "Cache", "Status", "Completed", ""].map((h) => (
                      <th key={h} className="text-left px-4 py-2 text-xs font-medium" style={{ color: "var(--text-muted)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {jobHistory.map((j) => (
                    <tr key={String(j.job_id)} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td className="px-4 py-2 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>{String(j.job_id).slice(0, 8)}...</td>
                      <td className="px-4 py-2 text-xs" style={{ color: "var(--text-primary)" }}>{String(j.start_date ?? "")} — {String(j.end_date ?? "")}</td>
                      <td className="px-4 py-2 text-xs" style={{ color: "var(--text-secondary)" }}>{Number(j.total_files ?? 0).toLocaleString()}</td>
                      <td className="px-4 py-2 text-xs" style={{ color: "var(--text-primary)" }}>{Number(j.total_rows ?? 0).toLocaleString()}</td>
                      <td className="px-4 py-2 text-xs" style={{ color: "var(--text-muted)" }}>{Number(j.cache_hits ?? 0)} hit / {Number(j.cache_misses ?? 0)} miss</td>
                      <td className="px-4 py-2">
                        <span className="text-xs px-2 py-0.5 rounded" style={{
                          backgroundColor: j.status === "completed" ? "var(--risk-low-bg)" : "var(--risk-high-bg)",
                          color: j.status === "completed" ? "var(--risk-low)" : "var(--risk-high)",
                        }}>{String(j.status)}</span>
                      </td>
                      <td className="px-4 py-2 text-xs" style={{ color: "var(--text-muted)" }}>{String(j.completed_at ?? "—").slice(0, 19)}</td>
                      <td className="px-4 py-2">
                        {j.status === "completed" && (
                          <button onClick={() => viewJobCharts(String(j.job_id))}
                            className="text-xs px-2 py-1 rounded border"
                            style={{ borderColor: "var(--brand-primary)", color: "var(--brand-primary)" }}>
                            View Charts
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {jobHistory.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>No fetch jobs yet. Go to Log Analyzer tab to fetch logs.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ══════════ Tab 4: Settings (3 Accordion Sections) ══════════ */}
      {tab === "settings" && (
        <div className="space-y-4">
          {/* ── Section 1: Log Analyzer Settings ── */}
          <AccordionItem title="Log Analyzer Settings" subtitle="Language, date range, cache, auto-fetch" defaultOpen={true}>
            <div className="space-y-4 pt-4">
              <div>
                <label className="text-xs font-medium block mb-2" style={{ color: "var(--text-secondary)" }}>Language Preference</label>
                <div className="flex gap-4">
                  {(["en", "tr"] as const).map((lang) => (
                    <label key={lang} className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="language" checked={appSettings.language === lang}
                        onChange={() => setAppSettings({ ...appSettings, language: lang })} />
                      <span className="text-sm" style={{ color: "var(--text-primary)" }}>{lang === "en" ? "English" : "Turkish"}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Akamai CP Code</label>
                <input type="text" value={appSettings.cp_code} onChange={(e) => setAppSettings({ ...appSettings, cp_code: e.target.value })}
                  className="w-full md:w-48 text-sm px-3 py-2 rounded border outline-none font-mono"
                  style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}
                  placeholder="e.g. 60890" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Default Date Range</label>
                  <select value={appSettings.default_date_range} onChange={(e) => setAppSettings({ ...appSettings, default_date_range: e.target.value as AppSettings["default_date_range"] })}
                    className="w-full text-sm px-3 py-2 rounded border outline-none"
                    style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                    <option value="7d">Last 7 days</option>
                    <option value="30d">Last 30 days</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Log Cache Retention</label>
                  <select value={appSettings.log_cache_retention} onChange={(e) => setAppSettings({ ...appSettings, log_cache_retention: e.target.value as AppSettings["log_cache_retention"] })}
                    className="w-full text-sm px-3 py-2 rounded border outline-none"
                    style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                    <option value="7">7 days</option>
                    <option value="14">14 days</option>
                    <option value="30">30 days</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Auto-Fetch Schedule</label>
                  <select value={appSettings.auto_fetch_schedule} onChange={(e) => setAppSettings({ ...appSettings, auto_fetch_schedule: e.target.value as AppSettings["auto_fetch_schedule"] })}
                    className="w-full text-sm px-3 py-2 rounded border outline-none"
                    style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                    <option value="disabled">Disabled</option>
                    <option value="6h">Every 6 hours</option>
                    <option value="12h">Every 12 hours</option>
                    <option value="daily">Daily</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-2 items-center pt-2">
                <button onClick={saveAppSettings} className="px-4 py-2 rounded text-sm font-medium"
                  style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
                  Save Settings
                </button>
                {appSettingsMsg && (
                  <span className="text-xs" style={{ color: "var(--risk-low)" }}>{appSettingsMsg}</span>
                )}
              </div>
            </div>
          </AccordionItem>

          {/* ── Section 2: AWS Settings ── */}
          <AccordionItem title="AWS Settings" subtitle="S3 Settings">
            <div className="space-y-4 pt-4">
              <PasswordField
                label="AWS Access Key ID"
                value={awsSettings.aws_access_key_id}
                onChange={(v) => setAwsSettings({ ...awsSettings, aws_access_key_id: v })}
                show={showAwsKey}
                onToggle={() => setShowAwsKey(!showAwsKey)}
              />
              <PasswordField
                label="AWS Secret Access Key"
                value={awsSettings.aws_secret_access_key}
                onChange={(v) => setAwsSettings({ ...awsSettings, aws_secret_access_key: v })}
                show={showAwsSecret}
                onToggle={() => setShowAwsSecret(!showAwsSecret)}
              />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>S3 Bucket</label>
                  <input type="text" value={awsSettings.s3_bucket} onChange={(e) => setAwsSettings({ ...awsSettings, s3_bucket: e.target.value })}
                    className="w-full text-sm px-3 py-2 rounded border outline-none"
                    style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}
                    placeholder="ssport-datastream" />
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>S3 Region</label>
                  <input type="text" value={awsSettings.aws_region} onChange={(e) => setAwsSettings({ ...awsSettings, aws_region: e.target.value })}
                    className="w-full text-sm px-3 py-2 rounded border outline-none"
                    style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}
                    placeholder="eu-central-1" />
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>S3 Prefix</label>
                  <input type="text" value={awsSettings.s3_prefix} onChange={(e) => setAwsSettings({ ...awsSettings, s3_prefix: e.target.value })}
                    className="w-full text-sm px-3 py-2 rounded border outline-none"
                    style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}
                    placeholder="logs/" />
                </div>
              </div>

              <div className="flex flex-wrap gap-2 items-center pt-2">
                <button onClick={testS3Connection} className="px-4 py-2 rounded text-sm font-medium border"
                  style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
                  Test S3 Connection
                </button>
                <button onClick={saveAwsSettings} className="px-4 py-2 rounded text-sm font-medium"
                  style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
                  Save AWS Settings
                </button>
                <button onClick={clearCredentials} className="px-4 py-2 rounded text-sm font-medium"
                  style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)", border: "1px solid var(--risk-high)" }}>
                  Clear Credentials
                </button>
                <RiskBadge level="HIGH" />
              </div>

              <TestResultBadge result={s3TestResult} />

              {settingsMsg && (
                <p className="text-xs mt-2" style={{ color: settingsMsg.includes("fail") || settingsMsg.includes("Failed") ? "var(--risk-high)" : "var(--risk-low)" }}>
                  {settingsMsg}
                </p>
              )}
            </div>
          </AccordionItem>

          {/* ── Section 3: GCP Settings ── */}
          <AccordionItem title="GCP (Google Cloud Platform) Settings" subtitle="BigQuery credentials and export">
            <div className="space-y-6 pt-4">
              {/* BigQuery Settings sub-section */}
              <div>
                <h4 className="text-xs font-semibold mb-3 uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>BigQuery Settings</h4>
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>GCP Project ID</label>
                      <input type="text" value={bqSettings.gcp_project_id} onChange={(e) => setBqSettings({ ...bqSettings, gcp_project_id: e.target.value })}
                        className="w-full text-sm px-3 py-2 rounded border outline-none"
                        style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                    </div>
                    <div>
                      <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>BigQuery Dataset</label>
                      <input type="text" value={bqSettings.bq_dataset_id} onChange={(e) => setBqSettings({ ...bqSettings, bq_dataset_id: e.target.value })}
                        className="w-full text-sm px-3 py-2 rounded border outline-none"
                        style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>GCP Service Account JSON</label>
                    <textarea value={bqSettings.gcp_service_account_json} onChange={(e) => setBqSettings({ ...bqSettings, gcp_service_account_json: e.target.value })}
                      rows={4}
                      className="w-full text-sm px-3 py-2 rounded border outline-none font-mono resize-y"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}
                      placeholder='{"type": "service_account", ...}' />
                  </div>
                  <div className="flex flex-wrap gap-2 items-center">
                    <button onClick={testBqConnection} className="px-4 py-2 rounded text-sm font-medium border"
                      style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
                      Test BigQuery Connection
                    </button>
                    <button onClick={saveBqSettings} className="px-4 py-2 rounded text-sm font-medium"
                      style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
                      Save GCP Settings
                    </button>
                  </div>

                  <TestResultBadge result={bqTestResult} />

                  {bqSettingsMsg && (
                    <p className="text-xs mt-2" style={{ color: bqSettingsMsg.includes("fail") || bqSettingsMsg.includes("Failed") ? "var(--risk-high)" : "var(--risk-low)" }}>
                      {bqSettingsMsg}
                    </p>
                  )}
                </div>
              </div>

              {/* BigQuery Export sub-section */}
              <div className="border-t pt-6" style={{ borderColor: "var(--border)" }}>
                <h4 className="text-xs font-semibold mb-3 uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>BigQuery Export</h4>

                {/* Category checkboxes */}
                <div className="mb-4">
                  <label className="text-xs font-medium block mb-2" style={{ color: "var(--text-secondary)" }}>Select Export Categories</label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {BQ_CATEGORIES.map((cat) => (
                      <label key={cat.name} className="flex items-start gap-2 p-2 rounded border cursor-pointer"
                        style={{ borderColor: bqCategories[cat.name] ? "var(--brand-primary)" : "var(--border)", backgroundColor: bqCategories[cat.name] ? "var(--brand-glow)" : "transparent" }}>
                        <input type="checkbox" checked={bqCategories[cat.name] ?? true}
                          onChange={(e) => setBqCategories({ ...bqCategories, [cat.name]: e.target.checked })}
                          className="mt-0.5" />
                        <div>
                          <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{cat.name}</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {cat.fields.map((f) => (
                              <span key={f} className="text-xs px-1.5 py-0.5 rounded" style={{ backgroundColor: "var(--background)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>{f}</span>
                            ))}
                          </div>
                          {cat.note && (
                            <p className="text-xs mt-1" style={{ color: "var(--risk-medium)" }}>&#9888; {cat.note}</p>
                          )}
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Export controls */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Source Job</label>
                    <select value={bqSelectedJob} onChange={(e) => { setBqSelectedJob(e.target.value); setBqTableId(`akamai_logs_${e.target.value}`); }}
                      className="w-full text-sm px-3 py-2 rounded border outline-none"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
                      <option value="">Select a job...</option>
                      {bqRecentJobs.map((j) => (
                        <option key={j.jobId} value={j.jobId}>{j.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>BQ Table ID</label>
                    <input type="text" value={bqTableId} onChange={(e) => setBqTableId(e.target.value)}
                      placeholder={bqSelectedJob ? `akamai_logs_${bqSelectedJob}` : "akamai_logs_{job_id}"}
                      className="w-full text-sm px-3 py-2 rounded border outline-none font-mono"
                      style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
                  </div>
                  <div className="flex items-end">
                    <button onClick={startBqExport} disabled={!bqSelectedJob || bqExportJob?.status === "running"}
                      className="px-4 py-2 rounded text-sm font-medium disabled:opacity-50"
                      style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
                      Export to BigQuery
                    </button>
                  </div>
                </div>

                {/* Export progress */}
                {bqExportJob && (
                  <div className="mb-4">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Export Job: {bqExportJob.job_id}</span>
                      <span className="text-xs" style={{ color: bqExportJob.status === "completed" ? "var(--risk-low)" : bqExportJob.status === "failed" ? "var(--risk-high)" : "var(--brand-primary)" }}>
                        {bqExportJob.status} {bqExportJob.status === "completed" && `— ${bqExportJob.rows_exported} rows`}
                      </span>
                    </div>
                    <div className="w-full h-2 rounded-full" style={{ backgroundColor: "var(--border)" }}>
                      <div className="h-2 rounded-full transition-all" style={{ width: `${bqExportProgress}%`, backgroundColor: bqExportJob.status === "failed" ? "var(--risk-high)" : "var(--brand-primary)" }} />
                    </div>
                    {bqExportJob.error && (
                      <p className="text-xs mt-1" style={{ color: "var(--risk-high)" }}>{bqExportJob.error}</p>
                    )}
                  </div>
                )}

                {/* Export history table */}
                <div className="rounded border overflow-x-auto" style={{ borderColor: "var(--border)" }}>
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border)" }}>
                        {["Job ID", "Table", "Rows", "Status", "Exported At"].map((h) => (
                          <th key={h} className="text-left px-4 py-2 text-xs font-medium" style={{ color: "var(--text-muted)" }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {bqHistory.map((h) => (
                        <tr key={h.job_id} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>{h.job_id}</td>
                          <td className="px-4 py-2 text-xs" style={{ color: "var(--text-secondary)" }}>{h.table_id}</td>
                          <td className="px-4 py-2 text-xs" style={{ color: "var(--text-primary)" }}>{h.rows_exported?.toLocaleString() ?? "—"}</td>
                          <td className="px-4 py-2">
                            <span className="text-xs px-2 py-0.5 rounded"
                              style={{
                                backgroundColor: h.status === "completed" ? "var(--risk-low-bg)" : h.status === "failed" ? "var(--risk-high-bg)" : "var(--risk-medium-bg)",
                                color: h.status === "completed" ? "var(--risk-low)" : h.status === "failed" ? "var(--risk-high)" : "var(--risk-medium)",
                              }}>
                              {h.status}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-xs" style={{ color: "var(--text-muted)" }}>{h.exported_at ?? "—"}</td>
                        </tr>
                      ))}
                      {bqHistory.length === 0 && (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>No exports yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </AccordionItem>
        </div>
      )}

      <AgentChatPanel appName="Log Analyzer" />
    </div>
  );
}
