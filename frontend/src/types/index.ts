// Shared TypeScript types for AAOP frontend

export type SeverityLevel = "P0" | "P1" | "P2" | "P3";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

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
  status: "open" | "investigating" | "resolved";
  sourceApp?: string;
  createdAt: string;
}
