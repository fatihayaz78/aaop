export interface CapacityMetric {
  id: string;
  service: string;
  metric_name: string;
  current_value: number;
  capacity_limit: number;
  utilization_pct: number;
  timestamp: string;
  region: string;
}
export interface CapacityDashboard {
  services_at_warning: number;
  services_at_critical: number;
  avg_utilization: number;
  peak_service: string;
  cost_estimate_monthly: number;
  utilization_by_service: { service: string; current: number; limit: number; pct: number }[];
  utilization_trend_24h: { hour: string; avg_pct: number }[];
}
