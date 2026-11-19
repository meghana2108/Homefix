import { describe, expect, it } from "vitest";
import type { HomeFixEvent } from "../contract";
import { newTurn, reduce } from "./reduce";

const status = (stage: string, ms: number | null = null) =>
  ({ type: "status", stage, detail: null, ms }) as HomeFixEvent;
const final: HomeFixEvent = {
  type: "final", answer: "4. Four", modality: "image", question_type: "count",
  latency_ms: 6214, profile: "full", model: "qwen3-vl:8b",
};

const run = (events: HomeFixEvent[]) => events.reduce(reduce, newTurn("how many mugs", ["mugs.jpg"]));

describe("reduce", () => {
  it("builds the answer from tokens and marks earlier stages done", () => {
    const t = run([status("converting"), status("generating"),
      { type: "token", text: "4" }, { type: "token", text: ". Four" }, final]);
    expect(t.answer).toBe("4. Four");
    expect(t.statuses).toHaveLength(2);
    expect(t.statuses[0].done).toBe(true);
    expect(t.final).toEqual(final);
    expect(t.statuses.every((s) => s.done)).toBe(true); // a final finishes the last chip
  });

  it("ignores an unknown event type and returns the same object", () => {
    const t = newTurn("x", []);
    expect(reduce(t, { type: "mystery" })).toBe(t);
  });

  it("stores a refusal", () => {
    const t = run([{ type: "refusal", reason: "safety", message: "Stop.", category: "gas" }]);
    expect(t.refusal?.reason).toBe("safety");
  });

  it("keeps the swap time on loading_model", () => {
    const t = run([status("loading_model", 6400)]);
    expect(t.statuses[0]).toEqual({ stage: "loading_model", detail: null, ms: 6400, done: false });
  });

  it("updates the same chip when a stage repeats with a detail", () => {
    const t = run([status("routing"), { type: "status", stage: "routing", detail: "Only the first file was used.", ms: null }]);
    expect(t.statuses).toHaveLength(1);
    expect(t.statuses[0].detail).toBe("Only the first file was used.");
  });

  it("uses final.answer when no tokens streamed (text answers)", () => {
    const t = run([{ ...final, answer: "Clean the filter." } as HomeFixEvent]);
    expect(t.answer).toBe("Clean the filter.");
  });

  it("stores the payload events", () => {
    const t = run([
      { type: "transcript", text: "hi", seconds: 1.2 },
      { type: "sound_labels", labels: [{ label: "beep", score: 0.7 }], is_speech: false },
      { type: "frames", timestamps: [0, 1.9] },
      { type: "citation", quote: "q", page: 12, source: "m.pdf", score: 100 },
      { type: "code_result", code: "c", passed: true, tests_run: 2, failures: 0, output_tail: "", attempts: 1 },
      { type: "error", stage: "generating", message: "oops", retryable: true },
    ]);
    expect([t.transcript?.text, t.soundLabels?.labels[0].label, t.frames?.timestamps.length,
      t.citation?.page, t.codeResult?.passed, t.error?.retryable]).toEqual(["hi", "beep", 2, 12, true, true]);
  });

  it("does not mutate the previous turn", () => {
    const t = newTurn("x", []);
    reduce(t, { type: "token", text: "a" });
    expect(t.answer).toBe("");
  });
});
