import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { routeOf } from "../App";
import type { HomeFixEvent } from "../contract";
import { newTurn, reduce } from "../state/reduce";
import { outcomeOf, stepsOf } from "../state/steps";
import { AnswerText, blocks } from "./AnswerText";
import { CitationCard } from "./CitationCard";
import { Landing } from "./landing/Landing";
import { formatSeconds } from "./LatencyBadge";
import { RefusalCard, safetySteps } from "./RefusalCard";
import { SentFiles } from "./SentFiles";
import { StartScreen } from "./Workspace";

const turnOf = (events: object[], files: string[] = []) =>
  (events as HomeFixEvent[]).reduce(reduce, newTurn("q", files));
const fin = (modality = "image", answer = "ok"): object =>
  ({ type: "final", answer, modality, question_type: "describe", latency_ms: 900, profile: "lite", model: "m" });
const st = (stage: string, detail: string | null = null, ms: number | null = null) => ({ type: "status", stage, detail, ms });

describe("routes", () => {
  it("#/ask is the workspace, everything else the front door", () => {
    expect(routeOf("#/ask")).toBe("ask");
    expect(routeOf("#/ask/x")).toBe("ask");
    expect(routeOf("")).toBe("landing");
    expect(routeOf("#why")).toBe("landing");
    expect(routeOf("#/asking")).toBe("landing");
  });
});

describe("steps: what happened, in words, from the real events", () => {
  it("the E21 photo: danger check, the manual it used, the code it read, the page it found", () => {
    const t = turnOf([st("converting"), st("safety_check"), st("routing"), st("routing", "Using the manual: Unit 4B guide"),
      st("generating", "found E21"), st("retrieving"), st("verifying"),
      { type: "citation", quote: "E21 - The washer cannot drain.", page: 2, source: "guide.pdf", score: 99 }, fin("homefix")],
    ["panel.jpg"]);
    const s = stepsOf(t);
    expect(s.map((x) => x.title)).toEqual(["Open your files", "Check for danger", "Choose how to answer", "Write the answer",
      "Search the manual", "Check the quote"]);
    expect(s.every((x) => x.state === "done")).toBe(true);
    expect(s.map((x) => x.result)).toEqual(["1 photo, ready.", "Nothing dangerous in your words.",
      "Using the manual: Unit 4B guide.", "Read E21 from the photo.", "Searched guide.pdf.", "Found word for word on page 2."]);
    expect(outcomeOf(t)).toMatchObject({ kind: "answered", label: "From the manual, page 2" });
  });

  it("danger stops at the check, in red", () => {
    const t = turnOf([st("converting"), st("safety_check"),
      { type: "refusal", reason: "safety", message: "Leave.", category: "fire" }, fin("none", "")]);
    const s = stepsOf(t);
    expect(s[1]).toMatchObject({ state: "stopped", result: "Signs of danger, so HomeFix stops here." });
    expect(outcomeOf(t).kind).toBe("danger");
  });

  it("no exact quote: the check step says so and the stamp is amber", () => {
    const t = turnOf([st("safety_check"), st("verifying"),
      { type: "refusal", reason: "not_in_document", message: "The document doesn't contain the answer.", category: null }, fin("text", "")]);
    expect(stepsOf(t).at(-1)).toMatchObject({ state: "notfound", result: "No exact quote, so no answer." });
    expect(outcomeOf(t)).toMatchObject({ kind: "notfound", label: "Not in the document" });
  });

  it("while working, the last step is running and the stamp says so", () => {
    const t = turnOf([st("safety_check"), st("labeling_sounds")]);
    expect(stepsOf(t).map((x) => x.state)).toEqual(["done", "running"]);
    expect(outcomeOf(t).kind).toBe("working");
  });

  it("a sound names the top match; code says how many examples passed", () => {
    const sound = turnOf([st("labeling_sounds"),
      { type: "sound_labels", labels: [{ label: "washing machine beeping", score: 0.62 }], is_speech: false }, fin("audio")]);
    expect(stepsOf(sound)[0].result).toBe("Most likely washing machine beeping (62%).");
    const code = turnOf([st("running_code"),
      { type: "code_result", code: "x", passed: true, tests_run: 3, failures: 0, output_tail: "", attempts: 1 }, fin("code", "")]);
    expect(stepsOf(code)[0].result).toBe("Passed 3 of 3 examples.");
    expect(outcomeOf(code).label).toBe("Code tested: passed 3 of 3");
  });
});

describe("the front door", () => {
  it("asks the question, offers one way in, and is honest about limits", () => {
    const { container } = render(<Landing />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Is it broken, or is it normal?");
    const ask = screen.getAllByRole("link", { name: "Ask about something at home" });
    expect(ask.length).toBeGreaterThan(0);
    ask.forEach((a) => expect(a).toHaveAttribute("href", "#/ask"));
    expect(screen.getByRole("heading", { name: "What HomeFix can't do" })).toBeInTheDocument();
    // no emoji anywhere: icons are lucide SVGs
    expect(container.textContent).not.toMatch(/\p{Extended_Pictographic}/u);
  });
});

describe("the start screen", () => {
  it("leads with the example gallery", () => {
    render(<StartScreen onTry={() => {}} />);
    expect(screen.getByRole("heading", { name: "Try an example" })).toBeInTheDocument();
  });
  it("a cited answer from an attached document says 'your document', not 'the manual'", () => {
    const t = turnOf([{ type: "citation", quote: "One cat is allowed.", page: 2, source: "lease.pdf", score: 99 }, fin("text")], ["lease.pdf"]);
    expect(outcomeOf(t).label).toBe("From your document, page 2");
  });
});

describe("AnswerText", () => {
  it("keeps a one-line count answer as a sentence, not a list", () => {
    expect(blocks("4. Four mugs on the shelf.")).toEqual([{ kind: "p", lines: ["4. Four mugs on the shelf."] }]);
  });
  it("turns 2+ numbered or bulleted lines into lists", () => {
    const { container } = render(<AnswerText text={"Do this:\n1. Unplug it.\n2. Clean the filter.\n\n- tip one\n- tip two"} />);
    expect(container.querySelectorAll("ol li")).toHaveLength(2);
    expect(container.querySelectorAll("ul li")).toHaveLength(2);
  });
  it("shows **bold** and never renders HTML from the model", () => {
    const { container } = render(<AnswerText text={"**Stop** now <img src=x onerror=alert(1)>"} />);
    expect(container.querySelector("strong")).toHaveTextContent("Stop");
    expect(container.querySelector("img")).toBeNull();
  });
  it("repeated identical lines are all kept", () => {
    expect(blocks("same\n\nsame")).toEqual([{ kind: "p", lines: ["same"] }, { kind: "p", lines: ["same"] }]);
  });
});

describe("cards and files", () => {
  it("shows a photo thumbnail, a sound player and a document chip", () => {
    const { container } = render(<SentFiles files={[
      { name: "panel.jpg", kind: "image", url: "blob:1" }, { name: "beep.wav", kind: "audio", url: "blob:2" },
      { name: "lease.pdf", kind: "file", url: null }]} />);
    expect(screen.getByAltText("panel.jpg")).toHaveAttribute("src", "blob:1");
    expect(container.querySelector("audio")).toHaveAttribute("src", "blob:2");
    expect(screen.getByText("lease.pdf")).toBeInTheDocument();
  });
  it("guesses the kind from the name when there is no preview", () => {
    expect(newTurn("q", ["a.JPG", "b.m4a", "c.mov", "d.csv"]).sentFiles.map((f) => f.kind)).toEqual(["image", "audio", "video", "file"]);
  });
  it("a refusal says what happened in its title", () => {
    render(<RefusalCard refusal={{ type: "refusal", reason: "not_in_document", message: "The document doesn't contain the answer.", category: null }} />);
    expect(screen.getByRole("status")).toHaveTextContent("The document doesn't say");
  });
  it("the safety card leads with Stop and lists the steps without the repeated opening", () => {
    render(<RefusalCard refusal={{ type: "refusal", reason: "safety", message: "Leave and call 911.", category: "fire" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/^Stop: this could be dangerous/);
    expect(safetySteps("⚠️ This could be dangerous. Stop using the appliance now. If there is smoke, leave and call 911."))
      .toEqual(["Stop using the appliance now.", "If there is smoke, leave and call 911."]);
  });
  it("a long quote folds, and opens on click", () => {
    const quote = "Clean the filter. ".repeat(40);
    const { container } = render(<CitationCard citation={{ type: "citation", quote, page: 3, source: "g.pdf", score: 99 }} />);
    expect(container.querySelector("blockquote")!.textContent!.length).toBeLessThan(340);
    fireEvent.click(screen.getByText("Show the full quote"));
    expect(container.querySelector("blockquote")).toHaveTextContent(quote.trim());
  });
  it("an instant answer doesn't say 0.0 s", () => {
    expect(formatSeconds(9)).toBe("under 0.1 s");
    expect(formatSeconds(6214)).toBe("6.2 s");
  });
});

describe("not in the document, without a quote check", () => {
  it("the last step turns amber and says why, and the card says what to try", () => {
    const t = turnOf([st("safety_check"), st("routing"), st("generating"),
      { type: "refusal", reason: "not_in_document", message: "The document doesn't contain the answer.", category: null }, fin("text", "")]);
    expect(stepsOf(t).at(-1)).toMatchObject({ state: "notfound", result: "No answer in the document." });
    render(<RefusalCard refusal={t.refusal!} />);
    expect(screen.getByRole("status")).toHaveTextContent("Try asking about the symptom instead");
  });
});
