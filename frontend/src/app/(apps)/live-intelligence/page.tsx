"use client";

import { useState, useEffect, useCallback } from "react";
import MetricCard from "@/components/ui/MetricCard";
import RiskBadge from "@/components/ui/RiskBadge";
import StatusDot from "@/components/ui/StatusDot";
import LogTable from "@/components/ui/LogTable";
import RechartsWrapper from "@/components/charts/RechartsWrapper";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";
import { apiGet, apiPost } from "@/lib/api";

type Tab = "calendar" | "monitor" | "prescale" | "sportradar" | "drm" | "epg";

export default function LiveIntelligence() {
  const [tab, setTab] = useState<Tab>("calendar");
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const [drm, setDrm] = useState<{ widevine: string; fairplay: string; playready: string }>({ widevine: "healthy", fairplay: "healthy", playready: "healthy" });
  const [showRegister, setShowRegister] = useState(false);
  const [newEvent, setNewEvent] = useState({ name: "", kickoff: "", viewers: "" });
  const [sportradarData, setSportradarData] = useState<Record<string, unknown>[]>([]);
  const [highlightRow, setHighlightRow] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [e, d] = await Promise.all([
        apiGet<Record<string, unknown>[]>("/live/events?tenant_id=bein_sports"),
        apiGet<{ widevine: string; fairplay: string; playready: string }>("/live/external/drm?tenant_id=bein_sports"),
      ]);
      setEvents(e);
      setDrm(d);
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Auto-refresh DRM every 60s
  useEffect(() => {
    if (tab !== "drm") return;
    const iv = setInterval(async () => {
      try { const d = await apiGet<typeof drm>("/live/external/drm?tenant_id=bein_sports"); setDrm(d); } catch {}
    }, 60000);
    return () => clearInterval(iv);
  }, [tab]);

  // Auto-refresh SportRadar every 30s
  useEffect(() => {
    if (tab !== "sportradar") return;
    const iv = setInterval(async () => {
      try {
        const d = await apiGet<Record<string, unknown>[]>("/live/external/sportradar?tenant_id=bein_sports");
        setSportradarData(d);
      } catch {}
    }, 30000);
    return () => clearInterval(iv);
  }, [tab]);

  const registerEvent = async () => {
    try {
      await apiPost("/live/events/register", { tenant_id: "bein_sports", event_name: newEvent.name, kickoff_time: newEvent.kickoff, expected_viewers: parseInt(newEvent.viewers) || 0 });
      setShowRegister(false);
      setNewEvent({ name: "", kickoff: "", viewers: "" });
      loadData();
    } catch {}
  };

  const drmStatus = (s: string) => s === "healthy" ? "active" as const : s === "degraded" ? "warning" as const : "error" as const;

  const TABS: { key: Tab; label: string }[] = [
    { key: "calendar", label: "Event Calendar" },
    { key: "monitor", label: "Live Monitor" },
    { key: "prescale", label: "Pre-Scale" },
    { key: "sportradar", label: "SportRadar" },
    { key: "drm", label: "DRM Status" },
    { key: "epg", label: "EPG" },
  ];

  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Live Intelligence</h2>

      <div className="flex gap-1 mb-6 border-b overflow-x-auto" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className="px-4 pb-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap"
            style={{ borderColor: tab === t.key ? "var(--brand-primary)" : "transparent", color: tab === t.key ? "var(--brand-primary)" : "var(--text-secondary)" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Calendar */}
      {tab === "calendar" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>This Week</p>
            <button onClick={() => setShowRegister(true)} className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Register Event</button>
          </div>
          <div className="grid grid-cols-7 gap-2 mb-6">
            {DAYS.map((d) => (
              <div key={d} className="rounded-lg border p-2 min-h-32" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>{d}</p>
                {events.filter(() => Math.random() > 0.7).slice(0, 1).map((ev, i) => (
                  <div key={i} className="rounded px-2 py-1 text-xs mb-1" style={{ backgroundColor: (ev.status === "live" ? "var(--risk-low-bg)" : ev.status === "completed" ? "rgba(72,79,88,0.15)" : "var(--brand-glow)"), color: (ev.status === "live" ? "var(--risk-low)" : ev.status === "completed" ? "var(--text-muted)" : "var(--brand-primary)") }}>
                    {String(ev.eventName || ev.event_name || "Event")}
                  </div>
                ))}
              </div>
            ))}
          </div>
          {showRegister && (
            <div className="fixed inset-0 z-50 flex justify-end" style={{ backgroundColor: "rgba(0,0,0,0.5)" }} onClick={() => setShowRegister(false)}>
              <div className="w-96 h-full p-6" style={{ backgroundColor: "var(--background-card)" }} onClick={(e) => e.stopPropagation()}>
                <h3 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Register Event</h3>
                <div className="space-y-4">
                  <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Event Name</label>
                    <input type="text" value={newEvent.name} onChange={(e) => setNewEvent({...newEvent, name: e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} /></div>
                  <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Kickoff</label>
                    <input type="datetime-local" value={newEvent.kickoff} onChange={(e) => setNewEvent({...newEvent, kickoff: e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} /></div>
                  <div><label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Expected Viewers</label>
                    <input type="number" value={newEvent.viewers} onChange={(e) => setNewEvent({...newEvent, viewers: e.target.value})} className="w-full text-sm px-3 py-2 rounded border outline-none" style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }} /></div>
                  <div className="flex gap-2 pt-4">
                    <button onClick={registerEvent} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>Register</button>
                    <button onClick={() => setShowRegister(false)} className="px-4 py-2 rounded text-sm border" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Live Monitor */}
      {tab === "monitor" && (
        <div>
          <div className="rounded-lg border p-6 mb-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>No live event in progress</p>
          </div>
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <RechartsWrapper data={[]} xKey="time" yKey="viewers" title="Concurrent Viewers (last 60 min)" color="var(--brand-primary)" />
          </div>
        </div>
      )}

      {/* Pre-Scale */}
      {tab === "prescale" && (
        <div>
          <div className="rounded-lg border p-4 mb-6" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Scale Recommendation</h3>
              <RiskBadge level="HIGH" />
            </div>
            <p className="text-sm mb-2" style={{ color: "var(--text-muted)" }}>No active scale recommendation.</p>
            <button onClick={() => confirm("Approve pre-scale? This is a HIGH risk action.")} className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>Approve Scale</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "event", label: "Event" }, { key: "factor", label: "Factor" }, { key: "triggeredAt", label: "Triggered" }, { key: "outcome", label: "Outcome" },
            ]} data={[]} />
          </div>
        </div>
      )}

      {/* SportRadar */}
      {tab === "sportradar" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>Auto-refresh: 30s</p>
            <button onClick={() => apiPost("/live/external/sync", { source: "sportradar", tenant_id: "bein_sports" })} className="text-xs px-3 py-1 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>Sync Now</button>
          </div>
          <div className="rounded-lg border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <LogTable columns={[
              { key: "matchId", label: "Match" }, { key: "homeTeam", label: "Home" }, { key: "awayTeam", label: "Away" }, { key: "score", label: "Score" }, { key: "minute", label: "Min" }, { key: "status", label: "Status" },
            ]} data={sportradarData} />
          </div>
        </div>
      )}

      {/* DRM Status */}
      {tab === "drm" && (
        <div>
          <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>Auto-refresh: 60s</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {(["widevine", "fairplay", "playready"] as const).map((p) => (
              <div key={p} className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold capitalize" style={{ color: "var(--text-primary)" }}>{p}</span>
                  <StatusDot status={drmStatus(drm[p])} label={drm[p]} />
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => confirm("Override DRM fallback? This is a HIGH risk action.")} className="px-4 py-1.5 rounded text-sm font-medium" style={{ backgroundColor: "var(--risk-high-bg)", color: "var(--risk-high)" }}>Override Fallback</button>
        </div>
      )}

      {/* EPG */}
      {tab === "epg" && (
        <div>
          <div className="flex justify-between mb-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Today&apos;s Schedule</p>
            <button onClick={() => apiPost("/live/external/sync", { source: "epg", tenant_id: "bein_sports" })} className="text-xs px-3 py-1 rounded" style={{ backgroundColor: "var(--brand-glow)", color: "var(--brand-primary)" }}>Sync EPG</button>
          </div>
          <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="grid grid-cols-1 gap-1">
              {Array.from({ length: 24 }, (_, h) => (
                <div key={h} className="flex items-center gap-3 py-1" style={{ borderBottom: "1px solid var(--border)" }}>
                  <span className="text-xs w-12 font-mono" style={{ color: "var(--text-muted)" }}>{String(h).padStart(2, "0")}:00</span>
                  <div className="flex-1 h-6 rounded" style={{ backgroundColor: h >= 8 && h <= 23 ? "var(--background-hover)" : "transparent" }} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <AgentChatPanel appName="Live Intelligence" />
    </div>
  );
}
