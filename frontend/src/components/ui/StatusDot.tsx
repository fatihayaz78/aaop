type Status = "active" | "warning" | "error" | "inactive";

const STATUS_COLORS: Record<Status, string> = {
  active: "var(--status-active)",
  warning: "var(--status-warning)",
  error: "var(--status-error)",
  inactive: "var(--status-inactive)",
};

export default function StatusDot({ status, label }: { status: Status; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="w-2 h-2 rounded-full inline-block"
        style={{ backgroundColor: STATUS_COLORS[status] }}
      />
      {label && (
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {label}
        </span>
      )}
    </span>
  );
}
