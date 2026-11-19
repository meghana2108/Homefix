import { describe, expect, it, vi } from "vitest";
import manifestText from "../public/manifest.webmanifest?raw";
import swSource from "../public/sw.js?raw";
import { wsUrl } from "./api/client";

describe("wsUrl", () => {
  const page = (origin: string) => ({ origin }) as Location;
  it("uses the API address when there is one", () => {
    expect(wsUrl("/api/mic", "http://127.0.0.1:8000", page("http://localhost:5173"))).toBe("ws://127.0.0.1:8000/api/mic");
  });
  it("uses the page's own address (wss on https) in the phone setup", () => {
    expect(wsUrl("/api/mic", "", page("https://10.0.0.84:5173"))).toBe("wss://10.0.0.84:5173/api/mic");
  });
});

describe("manifest", () => {
  it("has what browsers need to install the app", () => {
    const m = JSON.parse(manifestText);
    expect(m.display).toBe("standalone");
    expect(m.start_url).toBe("/");
    const sizes = m.icons.map((i: { sizes: string }) => i.sizes);
    expect(sizes).toContain("192x192");
    expect(sizes).toContain("512x512");
  });
});

describe("service worker", () => {
  type Handler = (e: unknown) => void;
  function load() {
    const handlers: Record<string, Handler> = {};
    const self = { addEventListener: (t: string, h: Handler) => { handlers[t] = h; }, location: { origin: "https://h:5173" } };
    const pending = () => new Promise(() => {});
    const caches = { match: pending, open: pending, keys: pending };
    new Function("self", "caches", "fetch", swSource)(self, caches, pending);
    return (url: string, method = "GET", mode = "cors") => {
      const respondWith = vi.fn();
      handlers.fetch({ request: { url, method, mode }, respondWith });
      return respondWith;
    };
  }

  it("never answers /api requests, so answers are never cached", () => {
    const fetchEvent = load();
    expect(fetchEvent("https://h:5173/api/chat", "POST")).not.toHaveBeenCalled();
    expect(fetchEvent("https://h:5173/api/health")).not.toHaveBeenCalled();
    expect(fetchEvent("https://h:5173/api/manuals")).not.toHaveBeenCalled();
  });

  it("serves the app shell", () => {
    const fetchEvent = load();
    expect(fetchEvent("https://h:5173/", "GET", "navigate")).toHaveBeenCalled();
    expect(fetchEvent("https://h:5173/assets/index-abc.js")).toHaveBeenCalled();
  });

  it("leaves other sites alone", () => {
    expect(load()("https://elsewhere.example/x.js")).not.toHaveBeenCalled();
  });
});
