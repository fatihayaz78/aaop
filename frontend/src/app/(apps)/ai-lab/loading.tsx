export default function Loading() {
  return (
    <div className="animate-pulse">
      <div className="h-8 w-48 rounded mb-6" style={{ backgroundColor: "var(--background-hover)" }} />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="rounded-lg p-4 border" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
            <div className="h-3 w-20 rounded mb-2" style={{ backgroundColor: "var(--background-hover)" }} />
            <div className="h-7 w-16 rounded" style={{ backgroundColor: "var(--background-hover)" }} />
          </div>
        ))}
      </div>
      <div className="rounded-lg border p-4" style={{ backgroundColor: "var(--background-card)", borderColor: "var(--border)" }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex gap-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
            <div className="h-4 w-24 rounded" style={{ backgroundColor: "var(--background-hover)" }} />
            <div className="h-4 w-40 rounded" style={{ backgroundColor: "var(--background-hover)" }} />
            <div className="h-4 w-16 rounded" style={{ backgroundColor: "var(--background-hover)" }} />
            <div className="h-4 w-20 rounded" style={{ backgroundColor: "var(--background-hover)" }} />
          </div>
        ))}
      </div>
    </div>
  );
}
