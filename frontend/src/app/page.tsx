export default function DashboardPage() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Dashboard</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[
          { title: "Active Incidents", value: "—", color: "var(--color-p0)" },
          { title: "CDN Health", value: "—", color: "var(--color-p3)" },
          { title: "Live Events", value: "—", color: "var(--color-brand-primary)" },
          { title: "Alert Queue", value: "—", color: "var(--color-p1)" },
          { title: "QoE Score", value: "—", color: "var(--color-p3)" },
          { title: "Agent Decisions (24h)", value: "—", color: "var(--color-text-secondary)" },
        ].map((card) => (
          <div
            key={card.title}
            className="bg-[var(--color-surface-card)] border border-[var(--color-border)] rounded-[var(--radius-md)] p-4"
          >
            <p className="text-sm text-[var(--color-text-muted)]">{card.title}</p>
            <p className="text-3xl font-bold mt-1" style={{ color: card.color }}>
              {card.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
