import MetricCard from "@/components/ui/MetricCard";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";

export default function GrowthRetention() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Growth & Retention</h2>
      <div className="flex gap-4 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {["Retention Dashboard", "Churn Risk", "Segments", "Data Analyst", "Insights"].map((tab, i) => (
          <button key={tab} className="pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: i === 0 ? "var(--brand-primary)" : "transparent", color: i === 0 ? "var(--brand-primary)" : "var(--text-secondary)" }}>{tab}</button>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Avg Churn Risk" value="—" trend="flat" />
        <MetricCard title="Retention (7d)" value="—" unit="%" trend="flat" />
        <MetricCard title="Retention (30d)" value="—" unit="%" trend="flat" />
        <MetricCard title="Active Segments" value="0" trend="flat" />
      </div>
      <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>No retention data available.</p>
      </div>
      <AgentChatPanel appName="Growth & Retention" />
    </div>
  );
}
