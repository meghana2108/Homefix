import type { HomeFixEvent } from "../contract";

/**
 * Parse server-sent events out of a text buffer.
 * Frames end with a blank line; `event:` names the type, `data:` lines hold JSON.
 * Returns the complete events and the unfinished tail to keep for the next chunk.
 * A frame that isn't valid JSON is dropped, never thrown.
 */
export function parseSSE(buffer: string): { events: HomeFixEvent[]; rest: string } {
  // sse-starlette ends lines with \r\n. Hold back a trailing \r: its \n may be in the next chunk.
  let held = "";
  if (buffer.endsWith("\r")) {
    held = "\r";
    buffer = buffer.slice(0, -1);
  }
  const text = buffer.replace(/\r\n?/g, "\n");
  const frames = text.split("\n\n");
  const rest = frames.pop() ?? "";
  const events: HomeFixEvent[] = [];
  for (const frame of frames) {
    const ev = parseFrame(frame);
    if (ev) events.push(ev);
  }
  return { events, rest: rest + held };
}

function parseFrame(frame: string): HomeFixEvent | null {
  let name = "";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line === "" || line.startsWith(":")) continue; // comment / keep-alive ping
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") name = value;
    else if (field === "data") data.push(value);
  }
  if (data.length === 0) return null;
  try {
    const parsed: unknown = JSON.parse(data.join("\n"));
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return null;
    const obj = parsed as Record<string, unknown>;
    if (typeof obj.type !== "string") {
      if (!name) return null;
      obj.type = name;
    }
    return obj as unknown as HomeFixEvent;
  } catch {
    return null;
  }
}
