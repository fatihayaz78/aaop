"use client";

export default function Header() {
  return (
    <header
      className="sticky top-0 z-10 flex items-center justify-between px-6 border-b"
      style={{
        height: "var(--header-height)",
        backgroundColor: "var(--background)",
        borderColor: "var(--border)",
      }}
    >
      <span className="text-sm" style={{ color: "var(--text-muted)" }}>
        AAOP Platform v1.0.0
      </span>

      <div className="flex items-center gap-4">
        {/* Tenant selector */}
        <select
          className="text-sm px-3 py-1 rounded border"
          style={{
            backgroundColor: "var(--background-card)",
            borderColor: "var(--border)",
            color: "var(--text-primary)",
          }}
          defaultValue="s_sport_plus"
        >
          <option value="s_sport_plus">S Sport Plus</option>
        </select>

        {/* User menu */}
        <div
          className="flex items-center gap-2 px-3 py-1 rounded"
          style={{ backgroundColor: "var(--background-card)" }}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
            style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}
          >
            A
          </div>
          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Admin
          </span>
        </div>
      </div>
    </header>
  );
}
