// Shared TypeScript types matching backend Pydantic models

export type SeverityLevel = "P0" | "P1" | "P2" | "P3";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type IncidentStatus = "open" | "investigating" | "resolved";

export interface TenantContext {
  tenantId: string;
  userId?: string;
  role?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}

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
}

export interface Incident {
  incidentId: string;
  tenantId: string;
  severity: SeverityLevel;
  title: string;
  status: IncidentStatus;
  sourceApp?: string;
  mttrSeconds?: number;
  createdAt: string;
}

export interface Alert {
  alertId: string;
  tenantId: string;
  severity: SeverityLevel;
  title: string;
  channel: string;
  status: string;
  sentAt: string;
}

export interface LiveEvent {
  eventId: string;
  eventName: string;
  sport: string;
  competition: string;
  kickoffTime: string;
  status: "scheduled" | "live" | "completed";
  expectedViewers: number;
}

export interface QoEMetrics {
  sessionId: string;
  qualityScore: number;
  bufferingRatio: number;
  startupTimeMs: number;
}

export interface RetentionScore {
  segmentId: string;
  churnRisk: number;
  retention7d: number;
  retention30d: number;
}

export interface CapacityForecast {
  metric: string;
  currentPct: number;
  predictedPct: number;
  trend: "stable" | "growing" | "declining";
}

export interface Experiment {
  experimentId: string;
  name: string;
  status: string;
  metric: string;
}

export interface SearchResult {
  docId: string;
  collection: string;
  title: string;
  content: string;
  relevanceScore: number;
}

export interface ServiceHealth {
  service: string;
  status: "healthy" | "degraded" | "down";
  latencyMs: number;
}

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
