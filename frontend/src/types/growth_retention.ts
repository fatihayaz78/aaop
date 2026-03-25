export interface RetentionScore {
  id: string;
  user_id_hash: string;
  churn_risk: number;
  qoe_score: number;
  segment: string;
  last_active: string;
  created_at: string;
}
export interface GrowthDashboard {
  total_users: number;
  at_risk_users: number;
  avg_churn_risk: number;
  avg_qoe_score: number;
  segment_breakdown: { power_user: number; regular: number; at_risk: number; churned: number };
  churn_trend_7d: { date: string; at_risk_count: number }[];
  top_churn_reasons: { reason: string; count: number }[];
}
