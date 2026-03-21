import MetricCard from "@/components/ui/MetricCard";
import StatusDot from "@/components/ui/StatusDot";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";

const APPS = [
  { name: "Ops Center", status: "active" as const, path: "/ops-center" },
  { name: "Log Analyzer", status: "active" as const, path: "/log-analyzer" },
  { name: "Alert Center", status: "active" as const, path: "/alert-center" },
  { name: "Viewer Experience", status: "active" as const, path: "/viewer-experience" },
  { name: "Live Intelligence", status: "active" as const, path: "/live-intelligence" },
  { name: "Growth & Retention", status: "active" as const, path: "/growth-retention" },
  { name: "Capacity & Cost", status: "active" as const, path: "/capacity-cost" },
  { name: "Admin & Governance", status: "active" as const, path: "/admin-governance" },
  { name: "AI Lab", status: "active" as const, path: "/ai-lab" },
  { name: "Knowledge Base", status: "active" as const, path: "/knowledge-base" },
  { name: "DevOps Assistant", status: "active" as const, path: "/devops-assistant" },
];

export default function DashboardPage() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>
        Platform Dashboard
      </h2>

      {/* Metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard title="Active Incidents" value="0" trend="flat" />
        <MetricCard title="Events (24h)" value="0" trend="flat" />
        <MetricCard title="Agent Decisions (24h)" value="0" trend="flat" />
        <MetricCard title="Avg QoE Score" value="—" unit="/5.0" trend="flat" />
      </div>

      {/* 11 Apps status grid */}
      <h3 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
        Applications
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 mb-8">
        {APPS.map((app) => (
          <a
            key={app.path}
            href={app.path}
            className="rounded-lg p-4 border transition-colors hover:border-[var(--brand-primary)]"
            style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {app.name}
              </span>
              <StatusDot status={app.status} />
            </div>
          </a>
        ))}
      </div>

      {/* Recent decisions feed */}
      <h3 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
        Recent Agent Decisions
      </h3>
      <div
        className="rounded-lg border p-4"
        style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
      >
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          No recent decisions. Connect to the backend to see live data.
        </p>
      </div>

      <AgentChatPanel appName="Platform" />
    </div>
  );
}
