"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet } from "@/lib/api";
import type { LiveEvent, LiveDashboard } from "@/types/live_intelligence";

type Tab = "dashboard" | "calendar" | "monitor" | "prescale" | "drm" | "epg";

const sportIcon: Record<string, string> = { football: "\u26BD", basketball: "\uD83C\uDFC0", motorsport: "\uD83C\uDFCE\uFE0F", tennis: "\uD83C\uDFBE" };

export default function LiveIntelligence() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [dash, setDash] = useState<LiveDashboard | null>(null);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [drm, setDrm] = useState<Record<string, unknown> | null>(null);
  const [sportradar, setSportradar] = useState<Record<string, unknown> | null>(null);
  const [epg, setEpg] = useState<Record<string, unknown> | null>(null);
  const [sportFilter, setSportFilter] = useState("");
  const [epgChannel, setEpgChannel] = useState("beIN Sports 1");

  const loadDash = useCallback(async () => {
    try { setDash(await apiGet<LiveDashboard>("/live/dashboard")); } catch { /* */ }
  }, []);

  const loadEvents = useCallback(async () => {
    try {
      const res = await apiGet<{ items: LiveEvent[] }>("/live/events?limit=50");
      setEvents(res.items ?? []);
    } catch { /* */ }
  }, []);

  useEffect(() => { loadDash(); loadEvents(); }, [loadDash, loadEvents]);

  useEffect(() => {
    if (tab === "drm") { (async () => { try { setDrm(await apiGet("/live/drm/status")); } catch { /* */ } })(); }
    if (tab === "dashboard") { (async () => { try { setSportradar(await apiGet("/live/sportradar")); } catch { /* */ } })(); }
    if (tab === "epg") { (async () => { try { setEpg(await apiGet("/live/epg")); } catch { /* */ } })(); }
  }, [tab]);

  // Poll dashboard 15s
  useEffect(() => {
    if (tab !== "dashboard" && tab !== "monitor") return;
    const i = setInterval(() => { loadDash(); loadEvents(); }, 15000);
    return () => clearInterval(i);
  }, [tab, loadDash, loadEvents]);

  const liveEvents = events.filter((e) => e.status === "live");
  const upcomingEvents = events.filter((e) => e.status === "scheduled");
  const completedEvents = events.filter((e) => e.status === "completed");
  const filteredEvents = sportFilter ? events.filter((e) => e.sport === sportFilter) : events;

  const fmtViewers = (n: number | null) => n ? `${(n / 1000).toFixed(0)}K` : "—";
  const fmtDate = (s: string) => { try { return new Date(s).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); } catch { return s; } };

  const TABS: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "Dashboard" }, { key: "calendar", label: "Event Calendar" },
    { key: "monitor", label: "Live Monitor" }, { key: "prescale", label: "Pre-Scale" },
    { key: "drm", label: "DRM Status" }, { key: "epg", label: "EPG" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Live Intelligence</h2>
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ═══ Dashboard ═══ */}
      {tab === "dashboard" && dash && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Live Now" value={dash.live_now_count} />
            <MetricCard title="Upcoming 24h" value={dash.upcoming_24h_count} />
            <MetricCard title="Pre-Scale Pending" value={dash.pre_scale_pending} />
            <MetricCard title="DRM Issues" value={dash.drm_issues} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <RechartsWrapper data={dash.events_timeline} xKey="hour" yKey="count" title="Events Timeline (24h)" height={200} type="line" />
            </div>
            <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <h3 className="text-xs font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Live Events</h3>
              {liveEvents.length === 0 ? (
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>No live events right now</p>
              ) : liveEvents.map((e) => (
                <div key={e.event_id} className="rounded border p-3 mb-2" style={{ borderColor: "var(--risk-high)", backgroundColor: "rgba(239,68,68,0.05)" }}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs px-2 py-0.5 rounded font-bold" style={{ backgroundColor: "#ef4444", color: "#fff" }}>LIVE</span>
                    <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{e.event_name || e.title}</span>
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>Viewers: {fmtViewers(e.peak_viewers)} | {e.competition}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ═══ Event Calendar ═══ */}
      {tab === "calendar" && (
        <div>
          <div className="flex gap-3 mb-4">
            <select value={sportFilter} onChange={(e) => setSportFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <option value="">All Sports</option>
              {["football", "basketball", "motorsport", "tennis"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="space-y-3">
            {filteredEvents.map((e) => (
              <div key={e.event_id} className="rounded-lg border p-4 flex items-center gap-4"
                style={{ backgroundColor: "var(--background-card)", borderColor: e.status === "live" ? "var(--risk-high)" : "var(--border)" }}>
                <span className="text-2xl">{sportIcon[e.sport] || "\uD83C\uDFC6"}</span>
                <div className="flex-1">
                  <h4 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{e.event_name || e.title}</h4>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>{e.competition} | {fmtDate(e.kickoff_time)}</p>
                </div>
                <div className="text-right">
                  <span className="text-xs px-2 py-0.5 rounded" style={{
                    backgroundColor: e.status === "live" ? "#ef4444" : e.status === "scheduled" ? "#3b82f6" : "var(--border)",
                    color: e.status === "completed" ? "var(--text-muted)" : "#fff",
                  }}>{e.status}</span>
                  <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{fmtViewers(e.expected_viewers)} expected</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ Live Monitor ═══ */}
      {tab === "monitor" && (
        <div>
          {liveEvents.length === 0 ? (
            <div className="rounded-lg border p-12 text-center" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>No live events right now</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {liveEvents.map((e) => (
                <div key={e.event_id} className="rounded-lg border p-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--risk-high)" }}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs px-2 py-0.5 rounded font-bold animate-pulse" style={{ backgroundColor: "#ef4444", color: "#fff" }}>LIVE</span>
                    <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{e.event_name || e.title}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                    <p>Viewers: <strong>{fmtViewers(e.peak_viewers)}</strong></p>
                    <p>Competition: {e.competition}</p>
                    <p>Sport: {sportIcon[e.sport] || ""} {e.sport}</p>
                    <p>DRM: <span style={{ color: "var(--risk-low)" }}>healthy</span></p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ Pre-Scale ═══ */}
      {tab === "prescale" && (
        <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Event", "Kickoff", "Expected Viewers", "Status", "Actions"].map((h) => (
                    <th key={h} className="text-left px-4 py-2 text-xs font-medium" style={{ color: "var(--text-muted)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {upcomingEvents.map((e) => (
                  <tr key={e.event_id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td className="px-4 py-2 text-xs" style={{ color: "var(--text-primary)" }}>{e.event_name || e.title}</td>
                    <td className="px-4 py-2 text-xs" style={{ color: "var(--text-muted)" }}>{fmtDate(e.kickoff_time)}</td>
                    <td className="px-4 py-2 text-xs" style={{ color: "var(--text-secondary)" }}>{fmtViewers(e.expected_viewers)}</td>
                    <td className="px-4 py-2 text-xs" style={{ color: e.pre_scale_done ? "var(--risk-low)" : "var(--risk-medium)" }}>{e.pre_scale_done ? "Scaled" : "Pending"}</td>
                    <td className="px-4 py-2">
                      <button onClick={() => alert("This action requires approval — contact NOC team")}
                        className="text-xs px-2 py-1 rounded border" style={{ borderColor: "var(--risk-medium)", color: "var(--risk-medium)" }}>
                        Trigger Pre-Scale
                      </button>
                    </td>
                  </tr>
                ))}
                {upcomingEvents.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>No upcoming events</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══ DRM Status ═══ */}
      {tab === "drm" && drm && (
        <div className="space-y-4">
          <div className="rounded-lg border p-3 text-center" style={{
            backgroundColor: (drm as any).overall_health === "healthy" ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
            borderColor: (drm as any).overall_health === "healthy" ? "#22c55e" : "#ef4444",
          }}>
            <span className="text-sm font-semibold" style={{ color: (drm as any).overall_health === "healthy" ? "#22c55e" : "#ef4444" }}>
              Overall DRM: {String((drm as any).overall_health).toUpperCase()}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {["widevine", "fairplay", "playready"].map((key) => {
              const d = (drm as any)[key] as Record<string, string> | undefined;
              const st = d?.status ?? "unknown";
              const color = st === "healthy" ? "#22c55e" : st === "degraded" ? "#eab308" : "#ef4444";
              return (
                <div key={key} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                  <h4 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>{key.charAt(0).toUpperCase() + key.slice(1)}</h4>
                  <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: color + "22", color }}>{st}</span>
                  {d?.license_server && <p className="text-xs mt-2 font-mono" style={{ color: "var(--text-muted)" }}>{d.license_server}</p>}
                  {d?.last_check && <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>Checked: {d.last_check.slice(11, 19)}</p>}
                </div>
              );
            })}
          </div>
          <button onClick={async () => { try { setDrm(await apiGet("/live/drm/status")); } catch { /* */ } }}
            className="px-3 py-1.5 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Refresh</button>
        </div>
      )}

      {/* ═══ EPG ═══ */}
      {tab === "epg" && epg && (
        <div>
          <div className="flex gap-2 mb-4">
            {((epg as any).channels ?? []).map((ch: any) => (
              <button key={ch.name} onClick={() => setEpgChannel(ch.name)}
                className="px-3 py-1.5 rounded text-xs font-medium"
                style={{ backgroundColor: epgChannel === ch.name ? "var(--brand-glow)" : "var(--background-card)",
                  color: epgChannel === ch.name ? "var(--brand-primary)" : "var(--text-secondary)", border: "1px solid var(--border)" }}>
                {ch.name}
              </button>
            ))}
          </div>
          {((epg as any).channels ?? []).filter((ch: any) => ch.name === epgChannel).map((ch: any) => (
            <div key={ch.name}>
              <div className="rounded-lg border p-4 mb-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--brand-primary)" }}>
                <h4 className="text-xs font-semibold mb-1" style={{ color: "var(--text-muted)" }}>Now Playing</h4>
                <p className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{ch.current?.title}</p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{ch.current?.start?.slice(11, 16)} — {ch.current?.end?.slice(11, 16)}</p>
              </div>
              <h4 className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>Up Next</h4>
              <div className="space-y-2">
                {(ch.next ?? []).map((p: any, i: number) => (
                  <div key={i} className="rounded border p-3 flex items-center gap-3" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                    <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>{p.start?.slice(11, 16)}</span>
                    <span className="text-sm" style={{ color: "var(--text-primary)" }}>{p.title}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <AgentChatPanel appName="Live Intelligence" />
    </div>
  );
}
