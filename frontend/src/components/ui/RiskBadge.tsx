type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

const RISK_CONFIG: Record<RiskLevel, { bg: string; color: string; label: string }> = {
  LOW: { bg: "var(--risk-low-bg)", color: "var(--risk-low)", label: "● AUTO" },
  MEDIUM: { bg: "var(--risk-medium-bg)", color: "var(--risk-medium)", label: "● AUTO+NOTIFY" },
  HIGH: { bg: "var(--risk-high-bg)", color: "var(--risk-high)", label: "● ONAY GEREKLİ" },
};

export default function RiskBadge({ level }: { level: RiskLevel }) {
  const config = RISK_CONFIG[level];
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
      style={{ backgroundColor: config.bg, color: config.color }}
    >
      {config.label}
    </span>
  );
}
