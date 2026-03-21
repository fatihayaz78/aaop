"use client";

import { useState, useEffect, useCallback } from "react";

interface SearchItem {
  type: "incident" | "alert" | "tenant" | "runbook";
  title: string;
  href: string;
  meta?: string;
}

const MOCK_ITEMS: SearchItem[] = [
  { type: "incident", title: "CDN Error Rate Spike", href: "/ops-center", meta: "P1 — open" },
  { type: "incident", title: "DRM Outage Widevine", href: "/ops-center", meta: "P0 — resolved" },
  { type: "alert", title: "QoE Degradation Alert", href: "/alert-center", meta: "P2 — active" },
  { type: "alert", title: "Churn Risk Detected", href: "/alert-center", meta: "P2 — acknowledged" },
  { type: "tenant", title: "beIN Sports", href: "/admin-governance", meta: "enterprise" },
  { type: "tenant", title: "Tivibu", href: "/admin-governance", meta: "growth" },
  { type: "runbook", title: "CDN Cache Purge Procedure", href: "/devops-assistant", meta: "runbook" },
  { type: "runbook", title: "Emergency Scale-Up", href: "/devops-assistant", meta: "runbook" },
];

const TYPE_LABELS: Record<string, string> = {
  incident: "Incidents",
  alert: "Alerts",
  tenant: "Tenants",
  runbook: "Runbooks",
};

export default function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      setOpen((prev) => !prev);
    }
    if (e.key === "Escape") setOpen(false);
  }, []);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const filtered = MOCK_ITEMS.filter(
    (item) => !query || item.title.toLowerCase().includes(query.toLowerCase()),
  );

  const grouped = Object.entries(TYPE_LABELS)
    .map(([type, label]) => ({
      label,
      items: filtered.filter((i) => i.type === type),
    }))
    .filter((g) => g.items.length > 0);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-24"
      style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-xl rounded-lg border shadow-2xl overflow-hidden"
        style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
          <span style={{ color: "var(--text-muted)" }}>🔍</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search incidents, alerts, tenants, runbooks..."
            className="flex-1 text-sm outline-none"
            style={{ backgroundColor: "transparent", color: "var(--text-primary)" }}
            autoFocus
          />
          <kbd
            className="text-xs px-1.5 py-0.5 rounded"
            style={{ backgroundColor: "var(--background-hover)", color: "var(--text-muted)" }}
          >
            ESC
          </kbd>
        </div>

        <div className="max-h-80 overflow-y-auto py-2">
          {grouped.length === 0 && (
            <p className="px-4 py-6 text-center text-sm" style={{ color: "var(--text-muted)" }}>
              No results found
            </p>
          )}
          {grouped.map((group) => (
            <div key={group.label}>
              <p
                className="px-4 pt-3 pb-1 text-xs font-semibold uppercase tracking-wider"
                style={{ color: "var(--text-muted)" }}
              >
                {group.label}
              </p>
              {group.items.map((item, i) => (
                <a
                  key={i}
                  href={item.href}
                  className="flex items-center justify-between px-4 py-2 transition-colors"
                  style={{ color: "var(--text-primary)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--background-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                  onClick={() => setOpen(false)}
                >
                  <span className="text-sm">{item.title}</span>
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>{item.meta}</span>
                </a>
              ))}
            </div>
          ))}
        </div>

        <div
          className="px-4 py-2 border-t flex justify-between"
          style={{ borderColor: "var(--border)" }}
        >
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            ↑↓ Navigate &middot; ↵ Open &middot; Esc Close
          </span>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            ⌘K to toggle
          </span>
        </div>
      </div>
    </div>
  );
}
