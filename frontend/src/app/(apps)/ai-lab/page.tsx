import MetricCard from "@/components/ui/MetricCard";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";

export default function AILab() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>AI Lab</h2>
      <div className="flex gap-4 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {["Experiments", "Model Registry", "Prompt Lab", "Evaluations", "Cost Tracker"].map((tab, i) => (
          <button key={tab} className="pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: i === 0 ? "var(--brand-primary)" : "transparent", color: i === 0 ? "var(--brand-primary)" : "var(--text-secondary)" }}>{tab}</button>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Active Experiments" value="0" trend="flat" />
        <MetricCard title="Models Registered" value="3" trend="flat" />
        <MetricCard title="Token Budget Used" value="—" unit="%" trend="flat" />
        <MetricCard title="Total Cost" value="—" unit="USD" trend="flat" />
      </div>
      <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>No experiments running.</p>
      </div>
      <AgentChatPanel appName="AI Lab" />
    </div>
  );
}
