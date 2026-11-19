import { describe, expect, it } from "vitest";
import { parseSSE } from "./sse";

describe("parseSSE", () => {
  it("returns complete events and keeps the unfinished tail", () => {
    const { events, rest } = parseSSE('event: token\ndata: {"type":"token","text":"Hi"}\n\nevent: fin');
    expect(events).toEqual([{ type: "token", text: "Hi" }]);
    expect(rest).toBe("event: fin");
  });

  it("handles CRLF line endings, as sse-starlette sends", () => {
    const { events, rest } = parseSSE(
      'event: status\r\ndata: {"type":"status","stage":"routing","detail":null,"ms":null}\r\n\r\n',
    );
    expect(events).toEqual([{ type: "status", stage: "routing", detail: null, ms: null }]);
    expect(rest).toBe("");
  });

  it("reads several events in one chunk", () => {
    const chunk =
      'event: token\ndata: {"type":"token","text":"4"}\n\n' +
      'event: token\ndata: {"type":"token","text":". Four"}\n\n';
    expect(parseSSE(chunk).events.map((e) => (e as { text: string }).text)).toEqual(["4", ". Four"]);
  });

  it("joins multi-line data and skips comments and pings", () => {
    const chunk = ': ping - 2026-11-18\n\nevent: token\ndata: {"type":"token",\ndata: "text":"a"}\n\n';
    expect(parseSSE(chunk).events).toEqual([{ type: "token", text: "a" }]);
  });

  it("drops a frame whose data isn't JSON instead of throwing", () => {
    expect(parseSSE("event: token\ndata: not json\n\n").events).toEqual([]);
  });

  it("fills a missing type from the event line", () => {
    expect(parseSSE('event: token\ndata: {"text":"x"}\n\n').events).toEqual([{ type: "token", text: "x" }]);
  });
});
