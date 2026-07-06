// SSE parser for chat/continue streaming (design 6.4, 7.13).
// Accumulates `token` events; preserves partial buffer on error/disconnect (Property 9).
import { API_BASE, getAccessToken } from "./client";

export interface SSEHandlers {
  onToken: (delta: string) => void;
  onDone?: (data: { message_id?: string; token_count?: number; finish_reason?: string }) => void;
  onError?: (data: { code?: string; message?: string }) => void;
}

export async function streamSSE(
  path: string,
  body: unknown,
  handlers: SSEHandlers,
  opts?: { accessToken?: string | null; signal?: AbortSignal },
): Promise<string> {
  const token = opts?.accessToken ?? getAccessToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body ?? {}),
    signal: opts?.signal,
  });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      message = j?.error?.message || j?.detail || message;
    } catch {
      /* ignore */
    }
    handlers.onError?.({ code: `HTTP_${res.status}`, message });
    return "";
  }
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let accumulated = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const evt = parseFrame(frame);
        if (!evt) continue;
        if (evt.event === "token") {
          accumulated += evt.data.delta ?? "";
          handlers.onToken(evt.data.delta ?? "");
        } else if (evt.event === "done") {
          handlers.onDone?.(evt.data);
        } else if (evt.event === "error") {
          handlers.onError?.(evt.data);
        }
      }
    }
  } catch (e) {
    // preserve accumulated partial (Property 9)
    handlers.onError?.({ code: "SSE_DISCONNECTED", message: String(e) });
  }
  return accumulated;
}

export function parseFrame(frame: string): { event: string; data: any } | null {
  let event = "message";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { event, data: JSON.parse(data) };
  } catch {
    return null;
  }
}
