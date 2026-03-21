"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

interface NavItem {
  label: string;
  href: string;
  icon: string;
}

interface NavGroup {
  title: string;
  priority: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: "Kritik",
    priority: "P0",
    items: [
      { label: "Ops Center", href: "/ops-center", icon: "📡" },
      { label: "Log Analyzer", href: "/log-analyzer", icon: "🔍" },
      { label: "Alert Center", href: "/alert-center", icon: "🔔" },
    ],
  },
  {
    title: "İş",
    priority: "P1",
    items: [
      { label: "Viewer Experience", href: "/viewer-experience", icon: "👁️" },
      { label: "Live Intelligence", href: "/live-intelligence", icon: "⚡" },
      { label: "Growth & Retention", href: "/growth-retention", icon: "📈" },
      { label: "Capacity & Cost", href: "/capacity-cost", icon: "⚙️" },
      { label: "Admin & Governance", href: "/admin-governance", icon: "🛡️" },
    ],
  },
  {
    title: "Gelecek",
    priority: "P2",
    items: [
      { label: "AI Lab", href: "/ai-lab", icon: "🧪" },
      { label: "Knowledge Base", href: "/knowledge-base", icon: "📚" },
      { label: "DevOps Assistant", href: "/devops-assistant", icon: "🤖" },
    ],
  },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const width = collapsed ? "var(--sidebar-collapsed)" : "var(--sidebar-width)";

  return (
    <aside
      className="fixed left-0 top-0 h-full flex flex-col z-20 transition-all duration-200"
      style={{
        width,
        backgroundColor: "var(--background-card)",
        borderRight: "1px solid var(--border)",
      }}
    >
      {/* Logo */}
      <div
        className="flex items-center justify-between px-4 border-b"
        style={{ height: "var(--header-height)", borderColor: "var(--border)" }}
      >
        {!collapsed && (
          <div>
            <h1 className="text-base font-bold" style={{ color: "var(--brand-primary)" }}>
              Captain logAR
            </h1>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              AAOP v1.0.0
            </p>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded hover:bg-[var(--background-hover)] transition-colors"
          style={{ color: "var(--text-secondary)" }}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "→" : "←"}
        </button>
      </div>

      {/* Dashboard link */}
      <nav className="flex-1 overflow-y-auto py-2 px-2">
        <Link
          href="/"
          className="flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors mb-2"
          style={{
            backgroundColor: pathname === "/" ? "var(--brand-glow)" : "transparent",
            color: pathname === "/" ? "var(--brand-primary)" : "var(--text-secondary)",
            borderRadius: "var(--radius-sm)",
          }}
        >
          <span>🏠</span>
          {!collapsed && <span>Dashboard</span>}
        </Link>

        {/* Nav groups */}
        {NAV_GROUPS.map((group) => (
          <div key={group.priority} className="mt-3">
            {!collapsed && (
              <p
                className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider"
                style={{ color: "var(--text-muted)" }}
              >
                {group.priority} — {group.title}
              </p>
            )}
            {group.items.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors"
                  style={{
                    backgroundColor: isActive ? "var(--brand-glow)" : "transparent",
                    color: isActive ? "var(--brand-primary)" : "var(--text-secondary)",
                    borderRadius: "var(--radius-sm)",
                  }}
                  title={collapsed ? item.label : undefined}
                >
                  <span>{item.icon}</span>
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}
