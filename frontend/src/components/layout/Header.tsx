"use client";

import { useAuth } from "@/contexts/AuthContext";

export default function Header() {
  const { activeServiceName, role, tenantName, isLoggedIn, logout } = useAuth();

  return (
    <header
      className="sticky top-0 z-10 flex items-center justify-between px-6 border-b"
      style={{
        height: "var(--header-height)",
        backgroundColor: "var(--background)",
        borderColor: "var(--border)",
      }}
    >
      <span className="text-sm" style={{ color: "var(--text-muted)" }}>
        AAOP Platform v1.0.0
      </span>

      <div className="flex items-center gap-3">
        {/* Active service badge */}
        {isLoggedIn && (
          <span
            className="text-xs px-2.5 py-1 rounded-full font-medium"
            style={{
              backgroundColor: "var(--brand-glow)",
              color: "var(--brand-primary)",
              border: "1px solid var(--brand-primary)",
            }}
          >
            {activeServiceName}
          </span>
        )}

        {/* User info */}
        <div
          className="flex items-center gap-2 px-3 py-1 rounded cursor-pointer"
          style={{ backgroundColor: "var(--background-card)" }}
          onClick={isLoggedIn ? logout : undefined}
          title={isLoggedIn ? "Logout" : ""}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
            style={{
              backgroundColor: role === "super_admin" ? "var(--brand-accent)" : "var(--brand-primary)",
              color: "#fff",
            }}
          >
            {role === "super_admin" ? "S" : "A"}
          </div>
          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {tenantName || (role === "super_admin" ? "Platform Admin" : "User")}
          </span>
        </div>
      </div>
    </header>
  );
}
