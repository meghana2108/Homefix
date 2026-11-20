import { describe, expect, it } from "vitest";
import { warmingText, type Health } from "../contract";

const h = (steps: { label: string; state: "waiting" | "loading" | "ready" | "failed" }[], done = false): Health => ({
  profile: "full", ollama: true, models: {}, loaded: [],
  warm: { ready: done && steps.every((s) => s.state === "ready"), done,
    steps: steps.map((s, i) => ({ name: `m${i}`, ms: null, ...s })) },
});

describe("getting ready", () => {
  it("names the model loading now and how far along it is", () => {
    expect(warmingText(h([{ label: "Vision model", state: "ready" }, { label: "Speech", state: "loading" },
      { label: "Sounds", state: "waiting" }]))).toBe("Getting ready: Speech (2 of 3)");
  });
  it("says nothing once every model is ready, or for a server that doesn't report it", () => {
    expect(warmingText(h([{ label: "Vision model", state: "ready" }], true))).toBeNull();
    expect(warmingText({ profile: "full", ollama: true, models: {}, loaded: [] })).toBeNull();
    expect(warmingText(null)).toBeNull();
  });
  it("says getting ready before the steps are listed", () => {
    expect(warmingText({ profile: "full", ollama: true, models: {}, loaded: [], warm: { ready: false, done: false, steps: [] } }))
      .toBe("Getting ready");
  });

  it("names a model that couldn't load", () => {
    expect(warmingText(h([{ label: "Vision model", state: "ready" }, { label: "Speech", state: "failed" }], true)))
      .toBe("Couldn't load: Speech");
  });
});
