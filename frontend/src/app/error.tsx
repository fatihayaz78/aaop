"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-4">
      <p className="text-sm" style={{ color: "var(--risk-high)" }}>
        Something went wrong: {error.message}
      </p>
      <button
        onClick={reset}
        className="px-4 py-2 rounded text-sm"
        style={{ backgroundColor: "var(--brand-primary)", color: "#fff" }}
      >
        Try again
      </button>
    </div>
  );
}
