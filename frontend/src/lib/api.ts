const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("aaop_token") ?? "";
}

function headers(tenantId: string): HeadersInit {
  return {
    Authorization: `Bearer ${getToken()}`,
    "X-Tenant-ID": tenantId,
    "Content-Type": "application/json",
  };
}

export async function apiGet<T>(path: string, tenantId: string = "ott_co"): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: headers(tenantId),
    next: { revalidate: 30 },
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown, tenantId: string = "ott_co"): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: headers(tenantId),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body: unknown, tenantId: string = "ott_co"): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "PATCH",
    headers: headers(tenantId),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function apiDelete(path: string, tenantId: string = "ott_co"): Promise<void> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "DELETE",
    headers: headers(tenantId),
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return apiGet("/health");
}

export function exportToCsv(data: Record<string, unknown>[], filename: string): void {
  if (data.length === 0) return;
  const keys = Object.keys(data[0]);
  const csv = [
    keys.join(","),
    ...data.map((row) => keys.map((k) => JSON.stringify(row[k] ?? "")).join(",")),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
