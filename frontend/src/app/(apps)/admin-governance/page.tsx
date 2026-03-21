import MetricCard from "@/components/ui/MetricCard";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";

export default function AdminGovernance() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Admin & Governance</h2>
      <div className="flex gap-4 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {["Tenants", "Module Config", "API Keys", "Audit Log", "Compliance", "Usage Stats"].map((tab, i) => (
          <button key={tab} className="pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: i === 0 ? "var(--brand-primary)" : "transparent", color: i === 0 ? "var(--brand-primary)" : "var(--text-secondary)" }}>{tab}</button>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Active Tenants" value="1" trend="flat" />
        <MetricCard title="Enabled Modules" value="11" trend="flat" />
        <MetricCard title="Audit Entries (24h)" value="0" trend="flat" />
        <MetricCard title="Compliance Score" value="—" unit="%" trend="flat" />
      </div>
      <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Connect to backend to view tenants.</p>
      </div>
      <AgentChatPanel appName="Admin & Governance" />
    </div>
  );
}
