import MetricCard from "@/components/ui/MetricCard";
import StatusDot from "@/components/ui/StatusDot";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";

export default function DevOpsAssistant() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>DevOps Assistant</h2>
      <div className="flex gap-4 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {["Assistant", "Diagnostics", "Deployments", "Runbooks"].map((tab, i) => (
          <button key={tab} className="pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: i === 0 ? "var(--brand-primary)" : "transparent", color: i === 0 ? "var(--brand-primary)" : "var(--text-secondary)" }}>{tab}</button>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Services" value="3" trend="flat" />
        <MetricCard title="Deployments (7d)" value="0" trend="flat" />
        <MetricCard title="Open Incidents" value="0" trend="flat" />
        <MetricCard title="Runbooks" value="0" trend="flat" />
      </div>
      <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
        <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Service Health</h3>
        {["FastAPI Backend", "Next.js Frontend", "Redis"].map((svc) => (
          <div key={svc} className="flex items-center justify-between py-1">
            <span className="text-sm" style={{ color: "var(--text-secondary)" }}>{svc}</span>
            <StatusDot status="active" label="Healthy" />
          </div>
        ))}
      </div>
      <AgentChatPanel appName="DevOps Assistant" />
    </div>
  );
}
