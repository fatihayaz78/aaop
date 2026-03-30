"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface TenantOption {
  id: string;
  name: string;
}

export default function LoginPage() {
  const router = useRouter();
  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/auth/tenants`)
      .then((r) => r.json())
      .then((data) => setTenants(data))
      .catch(() => {});
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_id: tenantId || null,
          email,
          password,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        setError(err.detail || "Giriş başarısız");
        setLoading(false);
        return;
      }

      const data = await res.json();
      localStorage.setItem("aaop_token", data.access_token);
      localStorage.setItem("aaop_tenant_id", data.tenant_id || "");
      localStorage.setItem("aaop_tenant_name", data.tenant_name || "");
      localStorage.setItem("aaop_service_id", data.active_service_id || "");
      localStorage.setItem("aaop_service_ids", JSON.stringify(data.service_ids || []));
      localStorage.setItem("aaop_role", data.role || "");

      router.push("/");
    } catch {
      setError("Sunucuya bağlanılamadı");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950">
      <div className="w-full max-w-md p-8 rounded-xl bg-zinc-900 border border-zinc-800 shadow-2xl">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white">Captain logAR</h1>
          <p className="text-sm text-zinc-400 mt-1">AAOP Platform Login</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">Tenant</label>
            <select
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Platform Admin (Super Admin)</option>
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1">E-posta</label>
            <input
              type="text"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@telco.demo"
              required
              className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-white text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1">Parola</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Captain2026!"
              required
              className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-white text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {error && (
            <div className="text-red-400 text-sm text-center bg-red-950/30 rounded-lg py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 text-white font-medium text-sm transition-colors"
          >
            {loading ? "Giriş yapılıyor..." : "Giriş Yap"}
          </button>
        </form>

        <p className="text-xs text-zinc-600 text-center mt-6">
          Super admin tenant seçmeden giriş yapabilir
        </p>
      </div>
    </div>
  );
}
