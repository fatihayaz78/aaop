import MetricCard from "@/components/ui/MetricCard";
import RiskBadge from "@/components/ui/RiskBadge";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";

export default function OpsCenter() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Ops Center</h2>
      <div className="flex gap-4 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {["Dashboard", "Incidents", "RCA"].map((tab, i) => (
          <button key={tab} className="pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: i === 0 ? "var(--brand-primary)" : "transparent", color: i === 0 ? "var(--brand-primary)" : "var(--text-secondary)" }}>{tab}</button>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Active Incidents" value="0" trend="flat" />
        <MetricCard title="MTTR (avg)" value="—" unit="min" trend="flat" />
        <MetricCard title="P0/P1 Open" value="0" trend="flat" />
        <MetricCard title="RCA Complete" value="0" trend="flat" />
      </div>
      <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
        <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Recent Decisions</h3>
        <div className="flex items-center justify-between py-2">
          <span className="text-sm" style={{ color: "var(--text-muted)" }}>No incidents to display</span>
          <RiskBadge level="LOW" />
        </div>
      </div>
      <AgentChatPanel appName="Ops Center" />
    </div>
  );
}
