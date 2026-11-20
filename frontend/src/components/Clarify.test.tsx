import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ClarifyEvent, HomeFixEvent } from "../contract";
import { newTurn, reduce } from "../state/reduce";
import { outcomeOf, stepsOf } from "../state/steps";
import { TurnView } from "./TurnView";

const SEEN = "8:32\nCOOKTOP ON\nOven Light";
const ASK: ClarifyEvent = {
  type: "clarify",
  question: "I don't see an error code. What would you like to know?",
  seen: SEEN,
  options: [
    { label: "What does “COOKTOP ON” mean?", message: 'What does "COOKTOP ON" mean?', manual_id: null },
    { label: "Describe the photo", message: "Describe the photo.", manual_id: null },
  ],
};
const FINAL = { type: "final", answer: ASK.question, modality: "image", question_type: "describe", latency_ms: 2000,
  profile: "lite", model: "m" };
const asked = (extra: object[] = []) => ([
  { type: "status", stage: "generating", detail: "m", ms: null }, ...extra, ASK, FINAL,
] as HomeFixEvent[]).reduce(reduce, newTurn("What is this?", ["stove.jpg"]));

describe("HomeFix asks instead of guessing", () => {
  it("keeps the question back on the turn, stamps it, and says so in the steps", () => {
    const t = asked();
    expect(t.clarify).toEqual(ASK);
    expect(outcomeOf(t)).toMatchObject({ kind: "ask", label: "HomeFix needs to know more" });
    expect(stepsOf(t).at(-1)?.result).toBe("Asked you instead of guessing.");
  });

  it("shows the question, what it read, and one-click replies, and no guessed answer", () => {
    const onReply = vi.fn();
    const t = asked([{ type: "token", text: "I can't tell." }]);
    render(<TurnView turn={t} onReply={onReply} canReply />);
    expect(screen.getByText(ASK.question)).toBeInTheDocument();
    expect(screen.getByText("What HomeFix could read")).toBeInTheDocument();
    expect(screen.getByText(/COOKTOP ON\s+Oven Light/)).toBeInTheDocument();
    expect(screen.queryByText("I can't tell.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "What does “COOKTOP ON” mean?" }));
    expect(onReply).toHaveBeenCalledWith(ASK.options[0]);
    expect(screen.getByText(/type your answer below/)).toBeInTheDocument();
  });

  it("an older question back can't be answered by click", () => {
    render(<TurnView turn={asked()} onReply={() => {}} canReply={false} />);
    screen.getAllByRole("button", { name: /COOKTOP|Describe/ }).forEach((b) => expect(b).toBeDisabled());
  });
});

// ---- the workspace sends the reply with the same photo ----
const sent: { message: string; files: string[]; manual: string | null }[] = [];
vi.mock("../api/client", () => ({
  API_LABEL: "http://test", IS_MOCK: false, wsUrl: (p: string) => `ws://test${p}`,
  getHealth: () => Promise.resolve({ status: "ok", profile: "lite", models: {} }),
  getManuals: () => Promise.resolve([]),
  streamChat: async (form: FormData, on: (ev: HomeFixEvent) => void) => {
    sent.push({ message: String(form.get("message")), files: form.getAll("files").map((f) => (f as File).name),
      manual: form.get("manual_id") as string | null });
    if (sent.length === 1) { on(ASK); on(FINAL as HomeFixEvent); return; }
    on({ ...FINAL, answer: "COOKTOP ON means a burner is on.", question_type: "qa" } as HomeFixEvent);
  },
}));

describe("replying", () => {
  beforeEach(() => { sent.length = 0; });
  afterEach(() => vi.restoreAllMocks());

  async function askAboutPhoto() {
    const { Workspace } = await import("./Workspace");
    render(<Workspace />);
    const photo = new File(["x"], "stove.jpg", { type: "image/jpeg" });
    fireEvent.drop(document.querySelector(".ws")!, { dataTransfer: { files: [photo], types: ["Files"] } });
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "What is this?" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /^Ask$/ })); });
    await waitFor(() => expect(screen.getByText(ASK.question)).toBeInTheDocument());
  }

  it("a one-click reply asks that question about the same photo", async () => {
    await askAboutPhoto();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "What does “COOKTOP ON” mean?" })); });
    expect(sent[1]).toEqual({ message: 'What does "COOKTOP ON" mean?', files: ["stove.jpg"], manual: null });
  });

  it("a typed reply goes with the first question and the same photo", async () => {
    await askAboutPhoto();
    expect(screen.getByText(/Answering HomeFix.s question, with your file/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "It's the clock on my cooktop" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /^Ask$/ })); });
    expect(sent[1]).toEqual({ message: "What is this?\nIt's the clock on my cooktop", files: ["stove.jpg"], manual: null });
  });

  it("the reply can be dropped to ask something new", async () => {
    await askAboutPhoto();
    fireEvent.click(screen.getByRole("button", { name: "Ask something new instead" }));
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "How do I reset a breaker?" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /^Ask$/ })); });
    expect(sent[1]).toMatchObject({ message: "How do I reset a breaker?", files: [] });
  });
});
