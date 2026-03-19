import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Captain logAR — AAOP",
  description: "AI-powered OTT platform operations",
};

const NAV_ITEMS = [
  { label: "Dashboard", href: "/" },
  { label: "Ops Center", href: "/ops-center" },
  { label: "Log Analyzer", href: "/log-analyzer" },
  { label: "Alert Center", href: "/alert-center" },
  { label: "Viewer Experience", href: "/viewer-experience" },
  { label: "Live Intelligence", href: "/live-intelligence" },
  { label: "Growth & Retention", href: "/growth-retention" },
  { label: "Capacity & Cost", href: "/capacity-cost" },
  { label: "AI Lab", href: "/ai-lab" },
  { label: "Knowledge Base", href: "/knowledge-base" },
  { label: "DevOps Assistant", href: "/devops-assistant" },
  { label: "Admin & Governance", href: "/admin-governance" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-screen">
        {/* Sidebar */}
        <aside
          className="fixed left-0 top-0 h-full bg-[var(--color-surface)] border-r border-[var(--color-border)] flex flex-col"
          style={{ width: "var(--sidebar-width)" }}
        >
          <div className="p-4 border-b border-[var(--color-border)]">
            <h1 className="text-lg font-bold text-[var(--color-brand-primary)]">
              Captain logAR
            </h1>
            <p className="text-xs text-[var(--color-text-muted)]">AAOP v0.1.0</p>
          </div>
          <nav className="flex-1 overflow-y-auto p-2">
            {NAV_ITEMS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="block px-3 py-2 rounded-[var(--radius-sm)] text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] transition-colors"
              >
                {item.label}
              </a>
            ))}
          </nav>
        </aside>

        {/* Main content */}
        <main
          className="flex-1"
          style={{ marginLeft: "var(--sidebar-width)" }}
        >
          <header
            className="sticky top-0 z-10 bg-[var(--color-bg)] border-b border-[var(--color-border)] flex items-center px-6"
            style={{ height: "var(--header-height)" }}
          >
            <span className="text-sm text-[var(--color-text-muted)]">
              AAOP Platform
            </span>
          </header>
          <div className="p-6">{children}</div>
        </main>
      </body>
    </html>
  );
}
