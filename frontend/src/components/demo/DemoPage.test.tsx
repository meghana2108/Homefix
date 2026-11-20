import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { HomeFixEvent, Modality, Stage } from "../../contract";
import { expandBeats } from "../../demo/beats";
import { SCENES, type Recording, type SceneId } from "../../demo/scenes";
import { DemoPage, STEP_MS } from "./DemoPage";

const st = (stage: Stage, detail: string | null = null): HomeFixEvent => ({ type: "status", stage, detail, ms: null });
const final = (answer: string, modality: Modality = "image"): HomeFixEvent => ({
  type: "final", answer, modality, question_type: "manual_lookup", latency_ms: 900, profile: "full", model: "m",
});
const citation: HomeFixEvent = { type: "citation", quote: "FIXTURE QUOTE about the drain", page: 3, source: "guide.pdf", score: 99 };

function rec(scene: SceneId, message: string, files: string[], events: HomeFixEvent[]): Recording {
  return { scene, recorded_at: "2026-11-20T11:28:17", profile: "full", request: { message, files, manual_id: null }, events };
}
const RECS: Partial<Record<SceneId, Recording>> = {
  photo: rec("photo", "PHOTO QUESTION", ["/samples/x.jpg"], [st("converting"), st("generating"), citation, final("Photo answer.")]),
  sound: rec("sound", "SOUND QUESTION", ["/samples/clip.wav"], [st("converting"), final("Sound answer.", "audio")]),
  video: rec("video", "VIDEO QUESTION", ["/samples/clip.mp4"], [
    st("extracting_frames"), { type: "frames", timestamps: [0.1, 2.9, 5.8] }, st("generating"), final("4 lights.", "video")]),
  code: rec("code", "CODE QUESTION", [], [
    st("generating"), st("running_code"),
    { type: "code_result", code: "def f_to_c(f):\n    return (f - 32) * 5 / 9\n", passed: true, tests_run: 2, failures: 0, output_tail: "", attempts: 1 },
    final("Converts F to C.", "code")]),
  honesty: rec("honesty", "HONESTY QUESTION", [], [
    st("converting"), { type: "refusal", reason: "not_in_document", message: "no", category: null }, final("", "text")]),
  danger: rec("danger", "DANGER QUESTION", [], [
    st("converting"), { type: "refusal", reason: "safety", message: "Stop. Leave now.", category: null }, final("", "none")]),
};
const flat = expandBeats(SCENES, RECS);
const press = (key: string, target: Element | Window = window) => fireEvent.keyDown(target, { key });
const pressN = (key: string, n: number) => { for (let i = 0; i < n; i++) press(key); };
const jump = (n: number) => press(String(n));
const mount = (recordings = RECS) => render(<DemoPage scenes={SCENES} recordings={recordings} />);
const tick = (steps: number) => { for (let i = 0; i < steps; i++) act(() => { vi.advanceTimersByTime(STEP_MS); }); };
const current = () => screen.getAllByRole("button").find((b) => b.getAttribute("aria-current") === "step")?.textContent;

let play: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  window.location.hash = "#/demo";
  play = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(() => Promise.resolve());
});
afterEach(() => { cleanup(); play.mockRestore(); });

describe("keys", () => {
  it("ArrowRight advances, ArrowLeft goes back, no wrap", () => {
    mount();
    const title = SCENES[0].beats[0] as { text: string };
    press("ArrowLeft");
    expect(screen.getByText(title.text)).toBeTruthy();
    pressN("ArrowRight", 2 * SCENES.length);
    expect(screen.getByRole("button", { name: "Proof" }).getAttribute("aria-current")).toBe("step");
    const last = document.body.innerHTML;
    press("ArrowRight");
    expect(document.body.innerHTML).toBe(last);
    press("ArrowLeft");
    expect(document.body.innerHTML).not.toBe(last);
    expect(screen.getByRole("button", { name: "Code" }).getAttribute("aria-current")).toBe("step");
  });

  it("Space finishes the scene, PageDown starts the next, PageUp goes back", () => {
    mount();
    press(" ");
    expect(screen.getAllByRole("img").length).toBeGreaterThan(0);
    expect(screen.getByText(/It runs on this laptop/)).toBeTruthy();
    press("PageDown");
    expect(screen.getByText("PHOTO QUESTION")).toBeTruthy();
    press("PageUp");
    expect(screen.getByText(/It runs on this laptop/)).toBeTruthy();
  });

  it("ArrowRight in the middle of a scene finishes it and stays on it", () => {
    mount();
    jump(2);
    expect(screen.queryByLabelText("Citation")).toBeNull();
    press("ArrowRight");
    expect(current()).toContain("Photo to manual");
    expect(screen.getByLabelText("Citation")).toBeTruthy();
    expect(screen.getByText("Photo answer.")).toBeTruthy();
  });

  it("ArrowLeft shows the previous scene complete", () => {
    mount();
    jump(3);
    press("ArrowLeft");
    expect(current()).toContain("Photo to manual");
    expect(screen.getByText("Photo answer.")).toBeTruthy();
  });

  it("number keys jump", () => {
    mount();
    jump(3);
    expect(screen.getByRole("button", { name: "Sound" }).getAttribute("aria-current")).toBe("step");
    expect(screen.getByText("SOUND QUESTION")).toBeTruthy();
  });

  it("scene strip click jumps", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Danger" }));
    expect(screen.getByText("DANGER QUESTION")).toBeTruthy();
  });

  it("Escape opens the app", () => {
    mount();
    press("Escape");
    expect(window.location.hash).toBe("#/ask");
  });

  it("keys are ignored in fields", () => {
    mount();
    const input = document.createElement("input");
    document.body.appendChild(input);
    fireEvent.keyDown(input, { key: "ArrowRight" });
    expect(screen.queryAllByRole("img")).toHaveLength(0);
    input.remove();
  });

  it("listeners removed on unmount", () => {
    const { unmount } = mount();
    unmount();
    window.location.hash = "#/demo";
    press("Escape");
    expect(window.location.hash).toBe("#/demo");
  });
});

describe("scenes", () => {
  it("photo scene builds up by itself, with no key press, and stops at the answer", () => {
    vi.useFakeTimers();
    try {
      mount();
      jump(2);
      expect(screen.getByText("PHOTO QUESTION")).toBeTruthy();
      expect(screen.queryByLabelText("Citation")).toBeNull();
      expect(screen.getByText("Recorded on the M4, full profile, 20 Nov 2026")).toBeTruthy();
      const cites = flat.findIndex((f) => f.scene === 1 && f.upTo === 3);
      const first = flat.findIndex((f) => f.scene === 1);
      tick(cites - first - 1);
      expect(screen.queryByLabelText("Citation")).toBeNull();
      tick(1);
      expect(screen.getByLabelText("Citation")).toBeTruthy();
      tick(20);
      expect(screen.getByText("Photo answer.")).toBeTruthy();
      expect(current()).toContain("Photo to manual"); // never runs on into the next scene
      expect(window.location.hash).toBe("#/demo/2");
    } finally {
      vi.useRealTimers();
    }
  });

  it("the first scene's slides also appear by themselves", () => {
    vi.useFakeTimers();
    try {
      mount();
      expect(screen.queryByText(/It runs on this laptop/)).toBeNull();
      tick(2);
      expect(screen.getAllByRole("img").length).toBeGreaterThan(0);
      expect(screen.getByText(/It runs on this laptop/)).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("video scene shows the clip, then the frame strip and the count", () => {
    mount();
    jump(4);
    expect(current()).toContain("Video");
    expect(screen.getByText("VIDEO QUESTION")).toBeTruthy();
    expect(document.querySelector('video[src="/samples/clip.mp4"]')).toBeTruthy();
    expect(document.querySelector(".framestrip")).toBeNull();
    press("ArrowRight");
    expect(document.querySelector(".framestrip")).toBeTruthy();
    expect(screen.getByText("4 lights.")).toBeTruthy();
  });

  it("video scene plays the clip by itself, muted", async () => {
    mount();
    await act(async () => { jump(4); });
    const v = document.querySelector<HTMLVideoElement>('video[src="/samples/clip.mp4"]')!;
    expect(play.mock.contexts).toContain(v);
    expect(v.muted).toBe(true);
  });

  it("other scenes do not play a video", async () => {
    mount();
    await act(async () => { jump(2); });
    expect(play.mock.contexts.some((c: unknown) => c instanceof HTMLVideoElement)).toBe(false);
  });

  it("code scene is 7: the question, then the tested function and its pass badge", () => {
    mount();
    jump(7);
    expect(current()).toContain("Code");
    expect(screen.getByText("CODE QUESTION")).toBeTruthy();
    expect(screen.queryByText(/Passed 2 of 2/)).toBeNull();
    press("ArrowRight");
    expect(screen.getAllByText(/Passed 2 of 2/).length).toBeGreaterThan(0);
    expect(screen.getByText(/return \(f - 32\) \* 5 \/ 9/)).toBeTruthy();
  });

  it("danger scene shows the stripe and no steps", () => {
    mount();
    jump(6);
    press("ArrowRight");
    expect(document.querySelector(".card--safety .hazard")).toBeTruthy();
    expect(screen.queryByLabelText("Citation")).toBeNull();
  });

  it("missing recording", () => {
    const { honesty: _h, ...rest } = RECS;
    mount(rest);
    jump(5);
    expect(screen.getByText("This scene hasn't been recorded. Run scripts/record_demo.py.")).toBeTruthy();
    jump(6);
    expect(screen.getByText("DANGER QUESTION")).toBeTruthy();
  });

  it("missing media", () => {
    mount();
    press("ArrowRight");
    const img = screen.getAllByRole("img")[0];
    fireEvent.error(img);
    expect(screen.getByText(/Run scripts\/fetch_real_samples\.py/)).toBeTruthy();
  });

  it("blocked audio shows a play button", async () => {
    play.mockImplementation(() => Promise.reject(new DOMException("x", "NotAllowedError")));
    mount();
    await act(async () => { jump(3); });
    const btn = await screen.findByRole("button", { name: "Play the sound" });
    play.mockImplementation(() => Promise.resolve());
    fireEvent.click(btn);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Play the sound" })).toBeNull());
  });

  it("credits", () => {
    mount();
    jump(8);
    press("ArrowRight");
    expect(screen.getByText("Photos and sounds: Wikimedia Commons, see ASSETS.md")).toBeTruthy();
    expect(document.querySelectorAll(".demo__scores tbody tr")).toHaveLength(8);
    expect(screen.getByText("100 practice questions, one run on the M4 (20261120-1009-full-all)")).toBeTruthy();
    expect(screen.getByText("Our own automated tests: 807 backend and 170 frontend, all passing on 20 Nov 2026.")).toBeTruthy();
    const table = document.querySelector(".demo__scores")!;
    expect([...table.querySelectorAll("thead th")].map((th) => th.textContent)).toEqual(["Test", "Full (M4)"]);
    expect(table.querySelectorAll("tbody tr td")).toHaveLength(8); // one score per row: M4 only
    expect(table.textContent).not.toMatch(/M2|lite/i);
  });

  it("the last slide names the front page's limits", () => {
    mount();
    jump(8);
    press("ArrowRight");
    for (const lead of ["It answers only from what you give it.", "Real manuals print error codes as pictures.", "It is a hackathon prototype."]) {
      expect(screen.getByText(lead)).toBeTruthy();
    }
  });

  it("scrolls the newest step into view on advance", () => {
    const fn = vi.fn();
    (Element.prototype as unknown as { scrollIntoView: unknown }).scrollIntoView = fn;
    mount();
    fn.mockClear();
    press("ArrowRight");
    expect(fn).toHaveBeenCalled();
    delete (Element.prototype as unknown as { scrollIntoView?: unknown }).scrollIntoView;
  });

  it("ignores key repeat", () => {
    mount();
    fireEvent.keyDown(window, { key: "ArrowRight", repeat: true });
    expect(screen.queryAllByRole("img")).toHaveLength(0);
  });

  it("an audio file that fails for another reason shows the missing-media text, not the play button", async () => {
    play.mockImplementation(() => Promise.reject(new DOMException("x", "NotSupportedError")));
    mount();
    await act(async () => { jump(3); });
    expect(await screen.findByText(/Run scripts\/fetch_real_samples\.py/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Play the sound" })).toBeNull();
  });

  it("leaving the sound scene before play() settles never shows the missing-sound note", async () => {
    let reject!: (e: unknown) => void;
    play.mockImplementation(() => new Promise((_, r) => { reject = r; }));
    mount();
    await act(async () => { jump(3); });
    await act(async () => { jump(4); });
    await act(async () => { reject(new DOMException("x", "AbortError")); });
    expect(screen.queryByText(/sound file is missing/)).toBeNull();
  });
});

describe("scene in the address", () => {
  it("starts at the scene named in the hash, shown complete", () => {
    window.location.hash = "#/demo/3";
    mount();
    expect(document.querySelector(".demo__hint")!.textContent).toContain(`3 / ${SCENES.length}`);
    expect(screen.getByText("Sound answer.")).toBeTruthy();
  });

  it("the address names the scene and changes with replaceState, not a new history entry", () => {
    const push = vi.spyOn(window.history, "pushState");
    mount();
    press("ArrowRight");
    expect(window.location.hash).toBe("#/demo/1");
    press("ArrowRight");
    expect(window.location.hash).toBe("#/demo/2");
    expect(push).not.toHaveBeenCalled();
    push.mockRestore();
  });

  it("garbage and out-of-range numbers clamp", () => {
    window.location.hash = "#/demo/abc";
    const a = mount();
    expect(document.querySelector(".demo__hint")!.textContent).toContain(`1 / ${SCENES.length}`);
    a.unmount();
    window.location.hash = "#/demo/999";
    mount();
    expect(document.querySelector(".demo__hint")!.textContent).toContain(`${SCENES.length} / ${SCENES.length}`);
  });
});

describe("page chrome", () => {
  it("root class is demo-page, not the landing card's demo", () => {
    const { container } = mount();
    expect(container.querySelector("main.demo-page")).toBeTruthy();
    expect(container.querySelector(".demo")).toBeNull();
  });

  it("shows the honesty scene's manual note", () => {
    mount();
    jump(5);
    expect(screen.getByText("Manual loaded: Unit 4B apartment guide")).toBeTruthy();
  });

  it("a clicked scene tab gives up focus so Space does not re-trigger it", () => {
    mount();
    const tab = screen.getByRole("button", { name: /Sound/ });
    tab.focus();
    fireEvent.click(tab);
    expect(document.activeElement).not.toBe(tab);
  });
});
