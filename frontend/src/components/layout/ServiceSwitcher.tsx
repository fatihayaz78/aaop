"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";

export default function ServiceSwitcher() {
  const { tenantName, activeServiceName, serviceIds, services, role, switchService } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const hasMultiple = serviceIds.length > 1 || role === "super_admin";
  const displayTenant = role === "super_admin" ? "Platform Admin" : tenantName || "—";
  const icon = role === "super_admin" ? "👑" : "🏢";

  return (
    <div ref={ref} className="relative px-3 py-2">
      <div
        className="flex items-center gap-2 text-sm rounded-lg px-3 py-2 cursor-pointer hover:bg-[var(--background-hover)]"
        style={{ backgroundColor: "var(--background-card)", border: "1px solid var(--border)" }}
        onClick={() => hasMultiple && setOpen(!open)}
        title={hasMultiple ? "Switch service" : `Active service: ${activeServiceName}`}
      >
        <span>{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{displayTenant}</p>
          <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
            {activeServiceName}
            {hasMultiple && <span className="ml-1 text-xs" style={{ color: "var(--text-muted)" }}>▼</span>}
          </p>
        </div>
      </div>

      {open && hasMultiple && (
        <div
          className="absolute left-3 right-3 mt-1 rounded-lg border shadow-xl z-50 py-1 max-h-64 overflow-y-auto"
          style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
        >
          {role === "super_admin" ? (
            <SuperAdminList services={services} activeId={activeServiceName} onSelect={(id) => { switchService(id); setOpen(false); }} />
          ) : (
            services.map((s) => (
              <button
                key={s.id}
                onClick={() => { switchService(s.id); setOpen(false); }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--background-hover)] flex items-center gap-2"
                style={{ color: s.name === activeServiceName ? "var(--brand-primary)" : "var(--text-secondary)" }}
              >
                {s.name === activeServiceName && <span className="text-xs">✓</span>}
                <span className={s.name === activeServiceName ? "font-medium" : ""}>{s.name}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function SuperAdminList({ services, activeId, onSelect }: {
  services: { id: string; name: string }[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  // Group by tenant prefix (simple heuristic from service data)
  const groups: Record<string, { id: string; name: string }[]> = {};
  const tenantMap: Record<string, string> = {
    sport_stream: "OTT Co",
    tv_plus: "Tel Co",
    music_stream: "Tel Co",
    fly_ent: "Airline Co",
  };

  for (const s of services) {
    const tenant = tenantMap[s.id] || "Other";
    if (!groups[tenant]) groups[tenant] = [];
    groups[tenant].push(s);
  }

  return (
    <>
      {Object.entries(groups).map(([tenant, svcs]) => (
        <div key={tenant}>
          <p className="px-3 py-1 text-xs font-semibold uppercase" style={{ color: "var(--text-muted)" }}>
            {tenant}
          </p>
          {svcs.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelect(s.id)}
              className="w-full text-left px-6 py-1.5 text-sm hover:bg-[var(--background-hover)] flex items-center gap-2"
              style={{ color: s.name === activeId ? "var(--brand-primary)" : "var(--text-secondary)" }}
            >
              {s.name === activeId && <span className="text-xs">✓</span>}
              <span className={s.name === activeId ? "font-medium" : ""}>{s.name}</span>
            </button>
          ))}
        </div>
      ))}
    </>
  );
}
