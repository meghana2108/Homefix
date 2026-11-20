import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { HomeFixEvent, Stage } from "../contract";
import { expandBeats, firstBeatOf, turnAt } from "./beats";
import { cutPoints } from "./cuts";
import { RECORDINGS, SCENES, type Recording } from "./scenes";
import { OUR_TESTS, PACK_ITEMS, SCORES } from "./scores";

const st = (stage: Stage, detail: string | null = null): HomeFixEvent => ({ type: "status", stage, detail, ms: null });
const tok: HomeFixEvent = { type: "token", text: "x" };
const citation: HomeFixEvent = { type: "citation", quote: "E21 means drain", page: 3, source: "guide", score: 99 };
const final: HomeFixEvent = {
  type: "final", answer: "Clean the filter.", modality: "image", question_type: "manual_lookup",
  latency_ms: 10, profile: "full", model: null,
};
const labels: HomeFixEvent = { type: "sound_labels", labels: [{ label: "smoke alarm chirp", score: 0.9 }], is_speech: false };
const refusal: HomeFixEvent = { type: "refusal", reason: "safety", message: "Stop.", category: null };

const photoRec = (events: HomeFixEvent[]): Recording => ({
  scene: "photo", recorded_at: "2026-11-20T21:40:00", profile: "full",
  request: { message: "What should I do?", files: ["/samples/washer_display_e21.jpg"], manual_id: "apartment_guide_unit_4b" },
  events,
});
const full = [st("a" as Stage), st("a" as Stage, "more"), st("b" as Stage), tok, tok, citation, final];
const rec = (scene: Recording["scene"]): Recording => ({ ...photoRec(full), scene });
const all = { photo: rec("photo"), sound: rec("sound"), video: rec("video"), honesty: rec("honesty"), danger: rec("danger"), code: rec("code") };

describe("cutPoints", () => {
  it("cuts on new stages, citation and final", () => expect(cutPoints(full)).toEqual([1, 3, 6, 7]));
  it("cuts on sound_labels and refusal", () => expect(cutPoints([st("a" as Stage), labels, refusal, final])).toEqual([1, 2, 3, 4]));
  it("a stage that comes back later gets its own cut", () =>
    expect(cutPoints([st("a" as Stage), st("b" as Stage), st("a" as Stage)])).toEqual([1, 2, 3]));
  it("empty gives none", () => expect(cutPoints([])).toEqual([]));
  it("no final, no cut at the end", () => expect(cutPoints([st("a" as Stage), tok])).toEqual([1]));
  it("last event that is a cut type still cuts", () => expect(cutPoints([tok, citation])).toEqual([2]));
});

describe("turnAt", () => {
  it("builds the turn up to the cut", () => {
    const t = turnAt(photoRec(full), 7);
    expect(t.citation).not.toBeNull();
    expect(t.final).not.toBeNull();
    expect(t.sentFiles[0]).toEqual({ name: "washer_display_e21.jpg", kind: "image", url: "/samples/washer_display_e21.jpg" });
    expect(turnAt(photoRec(full), 1).final).toBeNull();
  });
});

describe("expandBeats", () => {
  it("one beat per cut, with upTo", () => {
    const flat = expandBeats(SCENES, all);
    const photo = flat.filter((f) => f.scene === 1);
    expect(photo).toHaveLength(cutPoints(full).length);
    expect(photo.every((f) => f.kind === "turn" && f.upTo !== undefined)).toBe(true);
    expect(firstBeatOf(flat, 1)).toBe(3);
  });
  it("missing recording gives one missing beat, others unchanged", () => {
    const { photo: _p, ...rest } = all;
    void _p;
    const flat = expandBeats(SCENES, rest);
    expect(flat.filter((f) => f.scene === 1)).toEqual([{ scene: 1, kind: "missing", beat: null }]);
    expect(flat.filter((f) => f.scene !== 1)).toEqual(expandBeats(SCENES, all).filter((f) => f.scene !== 1));
  });
  it("empty or final-less recording is missing", () => {
    for (const events of [[], [st("a" as Stage), tok]]) {
      const flat = expandBeats(SCENES, { ...all, photo: photoRec(events) });
      expect(flat.filter((f) => f.scene === 1)).toEqual([{ scene: 1, kind: "missing", beat: null }]);
    }
  });
});

describe("SCENES", () => {
  it("ids in order", () => expect(SCENES.map((s) => s.id)).toEqual(["problem", "photo", "sound", "video", "honesty", "danger", "code", "proof"]));
  it("photo note", () =>
    expect(SCENES[1].note).toBe("Drawn by us: no openly licensed photo of an error display exists"));
  it("problem photos", () => {
    const b = SCENES[0].beats.find((x) => x.kind === "photos");
    expect(b && b.kind === "photos" && b.items.map((i) => i.src)).toEqual([
      "/samples/real_breaker_panel.jpg", "/samples/real_leaking_pipe.jpg",
      "/samples/real_thermostat_66.jpg", "/samples/real_smoke_detector.jpg",
    ]);
  });
  it("proof has scores and limits", () => {
    const kinds = SCENES[7].beats.map((b) => b.kind);
    expect(kinds).toContain("scores");
    expect(kinds).toContain("limits");
  });
  it("video scene says the clip is made by us", () =>
    expect(SCENES[3]).toMatchObject({ id: "video", title: "Video", note: "Made by us: no openly licensed clip of warning lights exists" }));
  it("code is scene 7", () => expect(SCENES[6]).toMatchObject({ id: "code", title: "Code" }));
  it("offline", () => expect(JSON.stringify(SCENES)).not.toMatch(/https?:\/\//));
  it("demo sources have no remote URLs", () => {
    for (const f of ["scores.ts", "beats.ts", "cuts.ts"])
      expect(readFileSync(`src/demo/${f}`, "utf8")).not.toMatch(/https?:\/\//);
  });
  it("RECORDINGS is an object", () => expect(typeof RECORDINGS).toBe("object"));
});

describe("SCORES", () => {
  it("rows cover every practice question once", () => {
    expect(PACK_ITEMS).toBe(100);
    expect(SCORES.reduce((n, s) => n + Number(s.full.split("/")[1]), 0)).toBe(PACK_ITEMS);
  });
  it("our own test counts", () => expect(OUR_TESTS).toEqual({ backend: 825, frontend: 174, on: "20 Nov 2026" }));
  it("eight rows", () => {
    expect(SCORES).toEqual([
      { row: "Image count", full: "14/15" }, { row: "Image, other questions", full: "8/10" },
      { row: "Sound top-1", full: "8/10" },
      { row: "Speech answers", full: "8/10" }, { row: "Text answers", full: "15/15" },
      { row: "Text refusals", full: "3/5" }, { row: "Code pass@1", full: "20/20" },
      { row: "Video (all metrics)", full: "11/15" },
    ]);
  });
});
