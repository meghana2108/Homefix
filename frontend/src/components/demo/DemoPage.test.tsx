import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { HomeFixEvent, Modality, Stage } from "../../contract";
import { expandBeats } from "../../demo/beats";
import { SCENES, type Recording, type SceneId } from "../../demo/scenes";
import { DemoPage } from "./DemoPage";

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
    pressN("ArrowRight", flat.length - 1);
    expect(screen.getByRole("button", { name: "Proof" }).getAttribute("aria-current")).toBe("step");
    const last = document.body.innerHTML;
    press("ArrowRight");
    expect(document.body.innerHTML).toBe(last);
    press("ArrowLeft");
    expect(document.body.innerHTML).not.toBe(last);
  });

  it("Space and PageDown advance; PageUp goes back", () => {
    mount();
    press(" ");
    expect(screen.getAllByRole("img").length).toBeGreaterThan(0); // photos beat
    press("PageDown");
    expect(screen.getByText(/It runs on this laptop/)).toBeTruthy();
    press("PageUp");
    expect(screen.queryByText(/It runs on this laptop/)).toBeNull();
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
  it("photo scene builds up, with the recording label", () => {
    mount();
    jump(2);
    expect(screen.getByText("PHOTO QUESTION")).toBeTruthy();
    expect(screen.queryByLabelText("Citation")).toBeNull();
    expect(screen.getByText("Recorded on the M4, full profile, 20 Nov 2026")).toBeTruthy();
    const cites = flat.findIndex((f) => f.scene === 1 && f.upTo === 3);
    const first = flat.findIndex((f) => f.scene === 1);
    pressN("ArrowRight", cites - first - 1);
    expect(screen.queryByLabelText("Citation")).toBeNull();
    press("ArrowRight");
    expect(screen.getByLabelText("Citation")).toBeTruthy();
  });

  it("danger scene shows the stripe and no steps", () => {
    mount();
    jump(5);
    pressN("ArrowRight", 2);
    expect(document.querySelector(".card--safety .hazard")).toBeTruthy();
    expect(screen.queryByLabelText("Citation")).toBeNull();
  });

  it("missing recording", () => {
    const { honesty: _h, ...rest } = RECS;
    mount(rest);
    jump(4);
    expect(screen.getByText("This scene hasn't been recorded. Run scripts/record_demo.py.")).toBeTruthy();
    jump(5);
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
    jump(6);
    pressN("ArrowRight", 2);
    expect(screen.getByText("Photos and sounds: Wikimedia Commons, see ASSETS.md")).toBeTruthy();
    expect(document.querySelectorAll(".demo__scores tbody tr")).toHaveLength(7);
  });

  it("the last slide names the front page's limits", () => {
    mount();
    jump(6);
    pressN("ArrowRight", 2);
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

describe("beat in the address", () => {
  it("starts at the beat named in the hash", () => {
    window.location.hash = "#/demo/5";
    mount();
    const hint = document.querySelector(".demo__hint")!;
    expect(hint.textContent).toContain(`5 / ${flat.length}`);
  });

  it("advancing writes the next beat with replaceState, not a new history entry", () => {
    const push = vi.spyOn(window.history, "pushState");
    mount();
    press("ArrowRight");
    expect(window.location.hash).toBe("#/demo/2");
    press("ArrowRight");
    expect(window.location.hash).toBe("#/demo/3");
    expect(push).not.toHaveBeenCalled();
    push.mockRestore();
  });

  it("garbage and out-of-range numbers clamp", () => {
    window.location.hash = "#/demo/abc";
    const a = mount();
    expect(document.querySelector(".demo__hint")!.textContent).toContain(`1 / ${flat.length}`);
    a.unmount();
    window.location.hash = "#/demo/999";
    mount();
    expect(document.querySelector(".demo__hint")!.textContent).toContain(`${flat.length} / ${flat.length}`);
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
    jump(4);
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
