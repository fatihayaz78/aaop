import MetricCard from "@/components/ui/MetricCard";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";

export default function CapacityCost() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Capacity & Cost</h2>
      <div className="flex gap-4 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {["Capacity Forecast", "Current Usage", "Automation Jobs", "Cost Analysis", "Thresholds"].map((tab, i) => (
          <button key={tab} className="pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: i === 0 ? "var(--brand-primary)" : "transparent", color: i === 0 ? "var(--brand-primary)" : "var(--text-secondary)" }}>{tab}</button>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="CPU Usage" value="—" unit="%" trend="flat" />
        <MetricCard title="Bandwidth" value="—" unit="%" trend="flat" />
        <MetricCard title="Cost (Today)" value="—" unit="USD" trend="flat" />
        <MetricCard title="Active Jobs" value="0" trend="flat" />
      </div>
      <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>No capacity alerts.</p>
      </div>
      <AgentChatPanel appName="Capacity & Cost" />
    </div>
  );
}
