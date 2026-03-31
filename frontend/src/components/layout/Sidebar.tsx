"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import ServiceSwitcher from "./ServiceSwitcher";

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
  {
    title: "Dev / Test",
    priority: "DEV",
    items: [
      { label: "NL Query", href: "/nl-query", icon: "💬" },
      { label: "Data Generation & Extraction", href: "/mock-data-gen", icon: "🗄️" },
    ],
  },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [kbExpanded, setKbExpanded] = useState(false);
  const pathname = usePathname();

  // Auto-expand KB when on knowledge-base page
  const isKbPage = pathname?.startsWith("/knowledge-base");
  const kbOpen = isKbPage || kbExpanded;
  const width = collapsed ? "var(--sidebar-collapsed)" : "var(--sidebar-width)";

  return (
    <>
    <aside
      className="fixed left-0 top-0 h-full flex-col z-20 transition-all duration-200 hidden md:flex"
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

      {/* Service Switcher */}
      {!collapsed && <ServiceSwitcher />}

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
          <div key={group.priority} className="mt-1">
            {group.items.map((item) => {
              const isActive = pathname === item.href;
              const isKb = item.href === "/knowledge-base";

              if (isKb && !collapsed) {
                return (
                  <div key={item.href}>
                    <div
                      className="flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors cursor-pointer"
                      style={{
                        backgroundColor: isActive ? "var(--brand-glow)" : "transparent",
                        color: isActive ? "var(--brand-primary)" : "var(--text-secondary)",
                        borderRadius: "var(--radius-sm)",
                      }}
                      onClick={() => setKbExpanded(!kbOpen)}
                    >
                      <span>{item.icon}</span>
                      <span className="flex-1">{item.label}</span>
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>{kbOpen ? "−" : "+"}</span>
                    </div>
                    <div style={{ maxHeight: kbOpen ? "100px" : "0", overflow: "hidden", transition: "max-height 0.2s ease" }}>
                      <Link href="/knowledge-base?view=faq"
                        className="flex items-center gap-2 ml-6 px-3 py-1.5 rounded text-xs transition-colors"
                        style={{
                          backgroundColor: isKbPage && (pathname + (typeof window !== "undefined" ? window.location.search : "")).includes("view=faq") ? "rgba(31,111,235,0.1)" : "transparent",
                          color: "var(--text-muted)",
                        }}>FAQ</Link>
                      <Link href="/knowledge-base?view=documents"
                        className="flex items-center gap-2 ml-6 px-3 py-1.5 rounded text-xs transition-colors"
                        style={{
                          backgroundColor: isKbPage && (typeof window !== "undefined" && window.location.search.includes("view=documents")) ? "rgba(31,111,235,0.1)" : "transparent",
                          color: "var(--text-muted)",
                        }}>Documents</Link>
                    </div>
                  </div>
                );
              }

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

    {/* Mobile bottom nav */}
    <nav
      className="fixed bottom-0 left-0 right-0 z-20 md:hidden flex justify-around border-t py-2"
      style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
    >
      {[
        { icon: "📡", href: "/ops-center", label: "Ops" },
        { icon: "🔍", href: "/log-analyzer", label: "Logs" },
        { icon: "🔔", href: "/alert-center", label: "Alerts" },
        { icon: "🛡️", href: "/admin-governance", label: "Admin" },
        { icon: "🤖", href: "/devops-assistant", label: "DevOps" },
      ].map((item) => {
        const isActive = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className="flex flex-col items-center gap-0.5 text-xs"
            style={{ color: isActive ? "var(--brand-primary)" : "var(--text-muted)" }}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
    </>
  );
}
