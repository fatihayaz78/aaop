export interface LiveEvent {
  event_id: string;
  event_name: string;
  title?: string;
  sport: string;
  sport_type?: string;
  competition: string;
  kickoff_time: string;
  status: "scheduled" | "live" | "completed";
  expected_viewers: number;
  peak_viewers: number | null;
  actual_viewers?: number | null;
  pre_scale_done: boolean;
  pre_scale_triggered?: boolean;
  drm_status?: string;
}
export interface LiveDashboard {
  live_now_count: number;
  upcoming_24h_count: number;
  total_events_7d: number;
  pre_scale_pending: number;
  drm_issues: number;
  peak_viewers_today: number;
  events_timeline: { hour: string; count: number }[];
}
