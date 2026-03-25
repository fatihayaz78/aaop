export interface Tenant {
  id: string;
  name: string;
  plan: "enterprise" | "pro" | "starter";
  status: "active" | "suspended";
  is_active?: number;
  created_at: string;
}
export interface AuditEntry {
  id: string;
  tenant_id: string;
  user_id: string;
  action: string;
  resource: string;
  status: "success" | "failed";
  ip_hash: string;
  created_at: string;
}
export interface ComplianceCheck {
  name: string;
  status: "pass" | "fail" | "warning";
  description: string;
  last_checked: string;
}
export interface AdminDashboard {
  total_tenants: number;
  active_tenants: number;
  total_users: number;
  audit_events_24h: number;
  failed_actions_24h: number;
  token_usage_today: { input: number; output: number; cost_usd: number };
  compliance_score: number;
  top_actions: { action: string; count: number }[];
}
