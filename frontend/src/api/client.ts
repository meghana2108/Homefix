import type { Health, HomeFixEvent, Manual } from "../contract";
import { parseSSE } from "./sse";

export const API_URL: string = (import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

/** True when the UI is pointed at the mock server (port 8001). */
export const IS_MOCK: boolean = /:8001$/.test(API_URL);

/** POST /api/chat and call onEvent for each SSE event as it arrives. */
export async function streamChat(
  form: FormData,
  onEvent: (e: HomeFixEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/chat`, { method: "POST", body: form, signal });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
    const { events, rest } = parseSSE(done ? buffer + "\n\n" : buffer);
    buffer = rest;
    events.forEach(onEvent);
    if (done) return;
  }
}

async function getJSON<T>(path: string, timeoutMs = 3000): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { signal: AbortSignal.timeout(timeoutMs) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const getHealth = (): Promise<Health> => getJSON<Health>("/api/health");
export const getManuals = (): Promise<Manual[]> => getJSON<Manual[]>("/api/manuals");
