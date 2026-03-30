"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ServiceInfo {
  id: string;
  name: string;
}

interface AuthState {
  userId: string;
  tenantId: string | null;
  tenantName: string | null;
  serviceIds: string[];
  activeServiceId: string;
  activeServiceName: string;
  role: "super_admin" | "tenant_admin" | "service_user";
  services: ServiceInfo[];
  isLoggedIn: boolean;
}

interface AuthContextValue extends AuthState {
  switchService: (serviceId: string) => Promise<void>;
  logout: () => void;
}

const defaultState: AuthState = {
  userId: "",
  tenantId: null,
  tenantName: null,
  serviceIds: [],
  activeServiceId: "sport_stream",
  activeServiceName: "Sport Stream",
  role: "service_user",
  services: [],
  isLoggedIn: false,
};

const AuthContext = createContext<AuthContextValue>({
  ...defaultState,
  switchService: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(defaultState);
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("aaop_token");
    if (!token) return;

    const tenantId = localStorage.getItem("aaop_tenant_id") || null;
    const tenantName = localStorage.getItem("aaop_tenant_name") || null;
    const serviceId = localStorage.getItem("aaop_service_id") || "sport_stream";
    const role = (localStorage.getItem("aaop_role") || "service_user") as AuthState["role"];
    let serviceIds: string[] = [];
    let services: ServiceInfo[] = [];
    try {
      serviceIds = JSON.parse(localStorage.getItem("aaop_service_ids") || "[]");
      services = JSON.parse(localStorage.getItem("aaop_services") || "[]");
    } catch { /* ignore */ }

    const activeService = services.find((s) => s.id === serviceId);

    setState({
      userId: "",
      tenantId,
      tenantName,
      serviceIds,
      activeServiceId: serviceId,
      activeServiceName: activeService?.name || serviceId,
      role,
      services,
      isLoggedIn: true,
    });
  }, []);

  const switchService = useCallback(async (serviceId: string) => {
    const token = localStorage.getItem("aaop_token");
    if (!token) return;

    const res = await fetch(`${API}/auth/switch-service`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ service_id: serviceId }),
    });
    if (!res.ok) return;

    const data = await res.json();
    localStorage.setItem("aaop_token", data.access_token);
    localStorage.setItem("aaop_service_id", data.active_service_id);
    localStorage.setItem("aaop_service_ids", JSON.stringify(data.service_ids));
    localStorage.setItem("aaop_services", JSON.stringify(data.services));

    const svc = (data.services as ServiceInfo[]).find((s) => s.id === data.active_service_id);
    setState((prev) => ({
      ...prev,
      activeServiceId: data.active_service_id,
      activeServiceName: svc?.name || data.active_service_id,
      serviceIds: data.service_ids,
      services: data.services,
    }));

    router.refresh();
  }, [router]);

  const logout = useCallback(() => {
    localStorage.removeItem("aaop_token");
    localStorage.removeItem("aaop_tenant_id");
    localStorage.removeItem("aaop_tenant_name");
    localStorage.removeItem("aaop_service_id");
    localStorage.removeItem("aaop_service_ids");
    localStorage.removeItem("aaop_services");
    localStorage.removeItem("aaop_role");
    setState(defaultState);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ ...state, switchService, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
