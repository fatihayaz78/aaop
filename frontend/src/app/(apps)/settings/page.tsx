"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const SECTORS = ["OTT", "Telecom", "Broadcast", "Airline", "Other"];
const P0_MODULES = new Set(["ops_center", "log_analyzer", "alert_center"]);

const ALL_MODULES = [
  { name: "ops_center", label: "Ops Center", priority: "P0" },
  { name: "log_analyzer", label: "Log Analyzer", priority: "P0" },
  { name: "alert_center", label: "Alert Center", priority: "P0" },
  { name: "viewer_experience", label: "Viewer Experience", priority: "P1" },
  { name: "live_intelligence", label: "Live Intelligence", priority: "P1" },
  { name: "growth_retention", label: "Growth & Retention", priority: "P1" },
  { name: "capacity_cost", label: "Capacity & Cost", priority: "P1" },
  { name: "admin_governance", label: "Admin & Governance", priority: "P1" },
  { name: "ai_lab", label: "AI Lab", priority: "P2" },
  { name: "knowledge_base", label: "Knowledge Base", priority: "P2" },
  { name: "devops_assistant", label: "DevOps Assistant", priority: "P2" },
];

function authHeaders() {
  const token = typeof window !== "undefined" ? localStorage.getItem("aaop_token") || "" : "";
  const tid = typeof window !== "undefined" ? localStorage.getItem("aaop_tenant_id") || "ott_co" : "ott_co";
  return { Authorization: `Bearer ${token}`, "X-Tenant-ID": tid, "Content-Type": "application/json" };
}

export default function SettingsPage() {
  const { role, tenantName, isLoggedIn, logout } = useAuth();
  const router = useRouter();
  const isAdmin = role === "tenant_admin" || role === "super_admin";

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Settings</h1>

      <SecuritySection onLogout={logout} />
      <AppearanceSection />
      {isAdmin && <SectorSection />}
      {isAdmin && <ModulesSection />}
    </div>
  );
}

// ── Security ────────────────────────────────────────────────

function SecuritySection({ onLogout }: { onLogout: () => void }) {
  const [current, setCurrent] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleChange(e: React.FormEvent) {
    e.preventDefault();
    setMsg(""); setErr("");
    if (newPw !== confirm) { setErr("Passwords do not match"); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/password`, {
        method: "PATCH", headers: authHeaders(),
        body: JSON.stringify({ current_password: current, new_password: newPw }),
      });
      if (!res.ok) { const d = await res.json(); setErr(d.detail || "Error"); return; }
      setMsg("Password updated. Logging out...");
      setTimeout(onLogout, 1500);
    } catch { setErr("Connection error"); } finally { setLoading(false); }
  }

  return (
    <Card title="Security" icon="🔒">
      <form onSubmit={handleChange} className="space-y-3">
        <Input label="Current Password" type="password" value={current} onChange={setCurrent} />
        <Input label="New Password" type="password" value={newPw} onChange={setNewPw} />
        <Input label="Confirm New Password" type="password" value={confirm} onChange={setConfirm} />
        {err && <p className="text-red-400 text-sm">{err}</p>}
        {msg && <p className="text-green-400 text-sm">{msg}</p>}
        <button type="submit" disabled={loading} className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700">
          {loading ? "Updating..." : "Change Password"}
        </button>
      </form>
    </Card>
  );
}

// ── Appearance ──────────────────────────────────────────────

function AppearanceSection() {
  const [theme, setTheme] = useState("dark");

  useEffect(() => {
    const saved = localStorage.getItem("captain-logar-theme") || "dark";
    setTheme(saved);
    document.documentElement.setAttribute("data-theme", saved);
  }, []);

  function toggle(t: string) {
    setTheme(t);
    localStorage.setItem("captain-logar-theme", t);
    document.documentElement.setAttribute("data-theme", t);
    document.documentElement.classList.toggle("dark", t === "dark");
  }

  return (
    <Card title="Appearance" icon="🎨">
      <div className="flex gap-3">
        {["dark", "light"].map((t) => (
          <button
            key={t}
            onClick={() => toggle(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
              theme === t ? "border-blue-500 text-blue-400" : "border-zinc-700 text-zinc-400"
            }`}
            style={{ backgroundColor: theme === t ? "var(--brand-glow)" : "var(--background-card)" }}
          >
            {t === "dark" ? "🌙 Dark" : "☀️ Light"}
          </button>
        ))}
      </div>
    </Card>
  );
}

// ── Sector ──────────────────────────────────────────────────

function SectorSection() {
  const [sector, setSector] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetch(`${API}/admin/platform/tenants`, { headers: authHeaders() })
      .then((r) => r.json())
      .then((data) => {
        const tid = localStorage.getItem("aaop_tenant_id");
        const t = data.find((d: any) => d.id === tid);
        if (t) setSector(t.sector || "OTT");
      })
      .catch(() => {});
  }, []);

  async function save() {
    setMsg("");
    const res = await fetch(`${API}/admin/tenant/sector`, {
      method: "PATCH", headers: authHeaders(),
      body: JSON.stringify({ sector }),
    });
    if (res.ok) setMsg("Sector updated");
  }

  return (
    <Card title="Tenant Sector" icon="🏢">
      <div className="flex items-center gap-3">
        <select
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          className="px-3 py-2 rounded-lg text-sm border"
          style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}
        >
          {SECTORS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <button onClick={save} className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500">
          Save
        </button>
        {msg && <span className="text-green-400 text-sm">{msg}</span>}
      </div>
    </Card>
  );
}

// ── Modules ─────────────────────────────────────────────────

function ModulesSection() {
  const [modules, setModules] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetch(`${API}/admin/modules`, { headers: authHeaders() })
      .then((r) => r.json())
      .then((data: any[]) => {
        const map: Record<string, boolean> = {};
        for (const m of data) map[m.module_name] = m.enabled;
        setModules(map);
      })
      .catch(() => {});
  }, []);

  async function toggle(moduleName: string, moduleId: string, enabled: boolean) {
    const res = await fetch(`${API}/admin/modules/${moduleId}`, {
      method: "PATCH", headers: authHeaders(),
      body: JSON.stringify({ enabled }),
    });
    if (res.ok) setModules((prev) => ({ ...prev, [moduleName]: enabled }));
  }

  return (
    <Card title="Module Management" icon="🧩">
      <div className="space-y-2">
        {ALL_MODULES.map((m) => {
          const isP0 = P0_MODULES.has(m.name);
          const enabled = modules[m.name] ?? true;
          return (
            <div key={m.name} className="flex items-center justify-between py-2 px-3 rounded-lg" style={{ backgroundColor: "var(--background)" }}>
              <div>
                <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{m.label}</span>
                <span className="ml-2 text-xs px-1.5 py-0.5 rounded" style={{
                  backgroundColor: m.priority === "P0" ? "rgba(239,68,68,0.15)" : m.priority === "P1" ? "rgba(234,179,8,0.15)" : "rgba(59,130,246,0.15)",
                  color: m.priority === "P0" ? "#ef4444" : m.priority === "P1" ? "#eab308" : "#3b82f6",
                }}>{m.priority}</span>
              </div>
              <div className="flex items-center gap-2">
                {isP0 && <span className="text-xs" style={{ color: "var(--text-muted)" }}>🔒</span>}
                <button
                  onClick={() => !isP0 && toggle(m.name, m.name, !enabled)}
                  disabled={isP0}
                  className={`w-10 h-5 rounded-full transition-colors relative ${isP0 ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
                  style={{ backgroundColor: enabled ? "var(--brand-primary)" : "var(--border)" }}
                >
                  <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${enabled ? "left-5" : "left-0.5"}`} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ── Shared components ───────────────────────────────────────

function Card({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border p-5" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
      <h2 className="text-base font-semibold mb-4 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
        <span>{icon}</span> {title}
      </h2>
      {children}
    </div>
  );
}

function Input({ label, type, value, onChange }: { label: string; type: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-sm mb-1" style={{ color: "var(--text-muted)" }}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded-lg text-sm border"
        style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--text-primary)" }}
      />
    </div>
  );
}
