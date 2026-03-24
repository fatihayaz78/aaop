// Shared TypeScript types matching backend Pydantic models

export type SeverityLevel = "P0" | "P1" | "P2" | "P3";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type IncidentStatus = "open" | "investigating" | "resolved";
export type AlertStatus = "active" | "acknowledged" | "resolved" | "suppressed";

export interface TenantContext {
  tenantId: string;
  userId?: string;
  role?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}

// ── Agent Decision ──
export interface AgentDecision {
  decisionId: string;
  tenantId: string;
  app: string;
  action: string;
  riskLevel: RiskLevel;
  approvalRequired: boolean;
  llmModelUsed: string;
  reasoningSummary?: string;
  confidenceScore?: number;
  durationMs?: number;
  createdAt: string;
  toolsExecuted?: string[];
  outputEventType?: string;
}

// ── Ops Center ──
export interface Incident {
  incidentId: string;
  tenantId: string;
  severity: SeverityLevel;
  title: string;
  status: IncidentStatus;
  sourceApp?: string;
  correlationIds?: string[];
  affectedServices?: string[];
  metricsAtTime?: Record<string, unknown>;
  rcaId?: string;
  mttrSeconds?: number;
  summaryTr?: string;
  detailEn?: string;
  resolvedAt?: string;
  createdAt: string;
  updatedAt?: string;
}

export interface OpsMetrics {
  openIncidents: number;
  mttrP50: number;
  activeTenants: number;
  decisionsLast24h: number;
  p0Open: number;
  p1Open: number;
  rcaComplete: number;
}

export interface RCAResult {
  rcaId: string;
  incidentId: string;
  rootCause: string;
  correlationIds: string[];
  remediationPlan?: string;
  summaryTr?: string;
  detailEn?: string;
  confidenceScore: number;
  status: string;
}

// ── Log Analyzer ──
export interface LogProject {
  projectId: string;
  tenantId: string;
  name: string;
  subModule: string;
  status: string;
  createdAt: string;
}

export interface FetchJob {
  jobId: string;
  job_id?: string;
  status: "queued" | "downloading" | "streaming" | "parsing" | "completed" | "failed" | "cancelled";
  progress?: number;
  total_files?: number;
  files_downloaded?: number;
  rows_parsed?: number;
  cache_hits?: number;
  cache_misses?: number;
  message?: string;
  error?: string;
}

export interface AnalysisResult {
  analysisId: string;
  projectId?: string;
  jobId?: string;
  errorRate: number;
  cacheHitRate: number;
  avgTtfbMs: number;
  totalRequests?: number;
  anomalies: { type: string; severity: string; description?: string }[];
  agentSummary?: string;
  reportPath?: string;
  createdAt?: string;
}

export interface ChartData {
  chartType: string;
  data: Record<string, unknown>[];
}

// ── Alert Center ──
export interface Alert {
  alertId: string;
  tenantId: string;
  severity: SeverityLevel;
  title: string;
  channel: string;
  status: AlertStatus;
  sourceApp?: string;
  decisionId?: string;
  sentAt: string;
  ackedAt?: string;
  resolvedAt?: string;
}

export interface AlertRule {
  id: string;
  tenantId: string;
  name: string;
  eventTypes: string;
  severityMin: string;
  channels: string;
  isActive: boolean;
}

export interface AlertChannel {
  id: string;
  tenantId: string;
  channelType: "slack" | "pagerduty" | "email";
  name: string;
  isActive: boolean;
}

export interface SuppressionRule {
  id: string;
  tenantId: string;
  name: string;
  startTime: string;
  endTime: string;
  isActive: boolean;
}

// ── Viewer Experience ──
export interface QoEMetrics {
  sessionId: string;
  qualityScore: number;
  bufferingRatio: number;
  startupTimeMs: number;
}

// ── Live Intelligence ──
export interface LiveEvent {
  eventId: string;
  eventName: string;
  sport: string;
  competition: string;
  kickoffTime: string;
  status: "scheduled" | "live" | "completed";
  expectedViewers: number;
}

// ── Growth & Retention ──
export interface RetentionScore {
  segmentId: string;
  churnRisk: number;
  retention7d: number;
  retention30d: number;
}

// ── Capacity & Cost ──
export interface CapacityForecast {
  metric: string;
  currentPct: number;
  predictedPct: number;
  trend: "stable" | "growing" | "declining";
}

// ── AI Lab ──
export interface Experiment {
  experimentId: string;
  name: string;
  status: string;
  metric: string;
}

// ── Knowledge Base ──
export interface SearchResult {
  docId: string;
  collection: string;
  title: string;
  content: string;
  relevanceScore: number;
}

// ── DevOps ──
export interface ServiceHealth {
  service: string;
  status: "healthy" | "degraded" | "down";
  latencyMs: number;
}

// ── Admin ──
export interface TenantInfo {
  tenantId: string;
  name: string;
  plan: string;
  isActive: boolean;
}

export interface ComplianceReport {
  totalDecisions: number;
  highRiskDecisions: number;
  approvalRate: number;
  violations: { type: string; count: number }[];
}
