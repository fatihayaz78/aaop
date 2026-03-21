"use client";

import { useState } from "react";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  const [showDetail, setShowDetail] = useState(false);

  return (
    <div className="flex flex-col items-center justify-center h-64 gap-4">
      <div className="text-3xl">⚠️</div>
      <p className="text-sm font-semibold" style={{ color: "var(--risk-high)" }}>
        Something went wrong
      </p>
      <button onClick={() => setShowDetail(!showDetail)} className="text-xs underline" style={{ color: "var(--text-muted)" }}>
        {showDetail ? "Hide details" : "Show details"}
      </button>
      {showDetail && (
        <pre className="text-xs p-3 rounded max-w-md overflow-auto" style={{ backgroundColor: "var(--background-card)", color: "var(--text-secondary)" }}>
          {error.message}
        </pre>
      )}
      <button onClick={reset} className="px-4 py-2 rounded text-sm font-medium" style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}>
        Try again
      </button>
    </div>
  );
}
