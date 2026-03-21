interface MetricCardProps {
  title: string;
  value: string | number;
  delta?: string;
  trend?: "up" | "down" | "flat";
  unit?: string;
}

export default function MetricCard({ title, value, delta, trend = "flat", unit }: MetricCardProps) {
  const trendColor =
    trend === "up" ? "var(--risk-low)" : trend === "down" ? "var(--risk-high)" : "var(--text-muted)";
  const trendIcon = trend === "up" ? "↑" : trend === "down" ? "↓" : "→";

  return (
    <div
      className="rounded-lg p-4 border"
      style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}
    >
      <p className="text-sm" style={{ color: "var(--text-muted)" }}>
        {title}
      </p>
      <p className="text-2xl font-bold mt-1" style={{ color: "var(--text-primary)" }}>
        {value}
        {unit && <span className="text-sm font-normal ml-1" style={{ color: "var(--text-secondary)" }}>{unit}</span>}
      </p>
      {delta && (
        <p className="text-xs mt-1" style={{ color: trendColor }}>
          {trendIcon} {delta}
        </p>
      )}
    </div>
  );
}
