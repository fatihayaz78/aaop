import type { SeverityLevel } from "@/types";

const SEVERITY_CONFIG: Record<SeverityLevel, { bg: string; color: string }> = {
  P0: { bg: "rgba(218, 54, 51, 0.15)", color: "var(--risk-high)" },
  P1: { bg: "rgba(210, 153, 34, 0.15)", color: "var(--risk-medium)" },
  P2: { bg: "rgba(31, 111, 235, 0.15)", color: "var(--brand-primary)" },
  P3: { bg: "rgba(72, 79, 88, 0.15)", color: "var(--text-muted)" },
};

export default function SeverityBadge({ severity }: { severity: SeverityLevel }) {
  const cfg = SEVERITY_CONFIG[severity];
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold"
      style={{ backgroundColor: cfg.bg, color: cfg.color }}
    >
      {severity}
    </span>
  );
}
