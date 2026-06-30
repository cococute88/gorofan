// Minimal typed API client (design 5.3, 6). SSE helper in sse.ts.
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", ...extra };
  if (accessToken) h["Authorization"] = `Bearer ${accessToken}`;
  return h;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: headers(), cache: "no-store" });
  if (!res.ok) throw await toError(res);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await toError(res);
  return res.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await toError(res);
  return res.json() as Promise<T>;
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE", headers: headers() });
  if (!res.ok && res.status !== 204) throw await toError(res);
}

async function toError(res: Response): Promise<Error> {
  try {
    const body = await res.json();
    return new Error(body?.error?.message || `HTTP ${res.status}`);
  } catch {
    return new Error(`HTTP ${res.status}`);
  }
}

export { API_BASE };
