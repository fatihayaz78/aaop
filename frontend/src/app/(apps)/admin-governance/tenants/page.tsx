"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface TenantService {
  id: string;
  name: string;
  status: string;
}

interface TenantRow {
  id: string;
  name: string;
  sector: string;
  status: string;
  services: TenantService[];
  user_count: number;
}

export default function PlatformTenantsPage() {
  const { role, isLoggedIn } = useAuth();
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoggedIn) return;
    const token = localStorage.getItem("aaop_token") || "";
    fetch(`${API}/admin/platform/tenants`, {
      headers: { Authorization: `Bearer ${token}`, "X-Tenant-ID": "ott_co" },
    })
      .then((r) => r.json())
      .then((data) => setTenants(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isLoggedIn]);

  if (role !== "super_admin") {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-400">Bu sayfaya erişim yetkiniz yok (super_admin gerekli)</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
          Platform Tenants
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Multi-tenant hierarchy overview
        </p>
      </div>

      {loading ? (
        <p style={{ color: "var(--text-muted)" }}>Loading...</p>
      ) : (
        <div
          className="rounded-lg border overflow-hidden"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--background-card)" }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th className="text-left px-4 py-3 font-medium" style={{ color: "var(--text-muted)" }}>Tenant</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: "var(--text-muted)" }}>Sector</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: "var(--text-muted)" }}>Services</th>
                <th className="text-center px-4 py-3 font-medium" style={{ color: "var(--text-muted)" }}>Users</th>
                <th className="text-center px-4 py-3 font-medium" style={{ color: "var(--text-muted)" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{t.name}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{t.sector}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                    {t.services.map((s) => s.name).join(", ")}
                  </td>
                  <td className="px-4 py-3 text-center" style={{ color: "var(--text-secondary)" }}>{t.user_count}</td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className="px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{
                        backgroundColor: t.status === "active" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                        color: t.status === "active" ? "#22c55e" : "#ef4444",
                      }}
                    >
                      {t.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
