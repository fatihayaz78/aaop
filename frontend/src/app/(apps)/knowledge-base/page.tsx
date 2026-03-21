import MetricCard from "@/components/ui/MetricCard";
import AgentChatPanel from "@/components/agent-chat/AgentChatPanel";

export default function KnowledgeBase() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Knowledge Base</h2>
      <div className="flex gap-4 mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {["Search", "Incidents", "Runbooks", "Ingest"].map((tab, i) => (
          <button key={tab} className="pb-2 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: i === 0 ? "var(--brand-primary)" : "transparent", color: i === 0 ? "var(--brand-primary)" : "var(--text-secondary)" }}>{tab}</button>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <MetricCard title="Incidents Indexed" value="0" trend="flat" />
        <MetricCard title="Runbooks" value="0" trend="flat" />
        <MetricCard title="Platform Docs" value="0" trend="flat" />
      </div>
      <div className="mb-6">
        <input type="text" placeholder="Search the knowledge base..."
          className="w-full text-sm px-4 py-3 rounded-lg border outline-none"
          style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)", color: "var(--text-primary)" }} />
      </div>
      <AgentChatPanel appName="Knowledge Base" />
    </div>
  );
}
