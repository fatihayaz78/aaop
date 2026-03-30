"use client";

import Link from "next/link";
import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";

export default function Header() {
  const { activeServiceName, role, tenantName, isLoggedIn, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

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

        {/* User menu with dropdown */}
        <div ref={menuRef} className="relative">
          <div
            className="flex items-center gap-2 px-3 py-1 rounded cursor-pointer"
            style={{ backgroundColor: "var(--background-card)" }}
            onClick={() => setMenuOpen(!menuOpen)}
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
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>▼</span>
          </div>

          {menuOpen && (
            <div
              className="absolute right-0 mt-1 w-44 rounded-lg border shadow-xl py-1 z-50"
              style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
            >
              <Link
                href="/settings"
                onClick={() => setMenuOpen(false)}
                className="block px-4 py-2 text-sm hover:bg-[var(--background-hover)]"
                style={{ color: "var(--text-secondary)" }}
              >
                Settings
              </Link>
              {isLoggedIn && (
                <button
                  onClick={() => { setMenuOpen(false); logout(); }}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-[var(--background-hover)]"
                  style={{ color: "var(--brand-accent)" }}
                >
                  Logout
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
