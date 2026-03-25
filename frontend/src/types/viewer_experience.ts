export interface QoEMetric {
  session_id: string;
  qoe_score: number;
  buffering_ratio: number;
  startup_time_ms: number;
  bitrate_avg: number;
  error_count: number;
  content_type: string;
  device_type: string;
  region: string;
  created_at: string;
}
export interface Complaint {
  id: string;
  title: string;
  category: string;
  sentiment: string;
  priority: string;
  status: string;
  created_at: string;
}
export interface ViewerDashboard {
  avg_qoe_score: number;
  sessions_below_threshold: number;
  active_complaints: number;
  total_sessions_24h: number;
  qoe_trend_24h: { hour: string; avg_score: number }[];
  score_distribution: { excellent: number; good: number; fair: number; poor: number };
  device_breakdown: { mobile: number; desktop: number; smarttv: number; tablet: number };
}
