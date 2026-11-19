import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { newTurn, reduce } from "../state/reduce";
import { AnswerText, blocks } from "./AnswerText";
import { Progress } from "./Progress";
import { RefusalCard } from "./RefusalCard";
import { SentFiles } from "./SentFiles";
import { TurnView } from "./TurnView";
import { SCENARIOS, WelcomeTiles } from "./WelcomeTiles";

describe("AnswerText", () => {
  it("keeps a one-line count answer as a sentence, not a list", () => {
    expect(blocks("4. Four mugs on the shelf.")).toEqual([{ kind: "p", lines: ["4. Four mugs on the shelf."] }]);
  });

  it("turns 2+ numbered or bulleted lines into lists", () => {
    const { container } = render(<AnswerText text={"Do this:\n1. Unplug it.\n2. Clean the filter.\n\n- tip one\n- tip two"} />);
    expect(container.querySelectorAll("ol li")).toHaveLength(2);
    expect(container.querySelectorAll("ul li")).toHaveLength(2);
    expect(container.querySelector("ol li")).toHaveTextContent("Unplug it.");
  });

  it("shows **bold** and never renders HTML from the model", () => {
    const { container } = render(<AnswerText text={"**Stop** now <img src=x onerror=alert(1)>"} />);
    expect(container.querySelector("strong")).toHaveTextContent("Stop");
    expect(container.querySelector("img")).toBeNull();
    expect(container).toHaveTextContent("<img src=x onerror=alert(1)>");
  });

  it("repeated identical lines are all kept", () => {
    expect(blocks("same\n\nsame")).toEqual([{ kind: "p", lines: ["same"] }, { kind: "p", lines: ["same"] }]);
  });
});

describe("Progress", () => {
  const s = (stage: string, done: boolean) => ({ stage: stage as never, detail: null, ms: null, done });

  it("says what it is doing in plain words while working", () => {
    render(<Progress statuses={[s("safety_check", true), s("labeling_sounds", false)]} done={false} />);
    expect(screen.getByText("Listening for sounds…")).toBeInTheDocument();
  });

  it("lists the checks that ran once done, and nothing technical", () => {
    const { container } = render(<Progress done statuses={[s("converting", true), s("safety_check", true), s("routing", true),
      s("retrieving", true), s("verifying", true)]} />);
    expect(container).toHaveTextContent("✓ Checked for danger · ✓ Searched the manual · ✓ Quote checked against the manual");
    expect(container).not.toHaveTextContent(/routing|converting/i);
  });
});

describe("SentFiles", () => {
  it("shows a photo thumbnail, a sound player and a document chip", () => {
    const { container } = render(<SentFiles files={[
      { name: "panel.jpg", kind: "image", url: "blob:1" },
      { name: "beep.wav", kind: "audio", url: "blob:2" },
      { name: "lease.pdf", kind: "file", url: null },
    ]} />);
    expect(screen.getByAltText("panel.jpg")).toHaveAttribute("src", "blob:1");
    expect(container.querySelector("audio")).toHaveAttribute("src", "blob:2");
    expect(screen.getByText("lease.pdf")).toBeInTheDocument();
  });

  it("guesses the kind from the name when there is no preview", () => {
    const t = newTurn("q", ["a.JPG", "b.m4a", "c.mov", "d.csv"]);
    expect(t.sentFiles.map((f) => f.kind)).toEqual(["image", "audio", "video", "file"]);
  });
});

describe("cards", () => {
  it("a refusal says what happened in its title", () => {
    render(<RefusalCard refusal={{ type: "refusal", reason: "not_in_document", message: "The document doesn't contain the answer.", category: null }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Not in the document");
  });

  it("a safety card leads with Stop", () => {
    render(<RefusalCard refusal={{ type: "refusal", reason: "safety", message: "Leave and call 911.", category: "fire" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/^⚠️ Stop: this could be dangerous/);
  });

  it("the pipeline steps and model sit behind 'How I got this'", () => {
    const turn = [
      { type: "status", stage: "safety_check", detail: null, ms: null },
      { type: "token", text: "Hi" },
      { type: "final", answer: "Hi", modality: "image", question_type: "describe", latency_ms: 900, profile: "lite", model: "m" },
    ].reduce((t, e) => reduce(t, e as never), newTurn("q", []));
    const { container } = render(<TurnView turn={turn} />);
    const how = container.querySelector("details.how")!;
    expect(how.querySelector("summary")).toHaveTextContent("How I got this");
    expect(how).toHaveTextContent("Model: m · ran on this laptop");
  });
});

describe("WelcomeTiles", () => {
  it("shows the renter's problems and covers every capability", () => {
    render(<WelcomeTiles onPick={() => {}} />);
    expect(screen.getByText("An error code on the display")).toBeInTheDocument();
    expect(new Set(SCENARIOS.map((s) => s.attach ?? "text"))).toEqual(new Set(["image", "audio", "video", "text"]));
    expect(SCENARIOS.some((s) => /function/i.test(s.example))).toBe(true);  // code
  });

  it("picking a card passes its question and the kind of file to attach", () => {
    const onPick = vi.fn();
    render(<WelcomeTiles onPick={onPick} />);
    fireEvent.click(screen.getByText("A beep or a strange noise"));
    expect(onPick).toHaveBeenCalledWith("What is this sound?", "audio");
  });
});

describe("polish", () => {
  it("the safety card drops the repeated opening line and lists the steps", async () => {
    const { safetySteps } = await import("./RefusalCard");
    expect(safetySteps("⚠️ This could be dangerous. Stop using the appliance now. If there is smoke, leave and call 911."))
      .toEqual(["Stop using the appliance now.", "If there is smoke, leave and call 911."]);
  });

  it("a long quote folds, and opens on click", async () => {
    const { CitationCard } = await import("./CitationCard");
    const quote = "Clean the filter. ".repeat(40);
    const { container } = render(<CitationCard citation={{ type: "citation", quote, page: 3, source: "g.pdf", score: 99 }} />);
    expect(container.querySelector("blockquote")!.textContent!.length).toBeLessThan(340);
    fireEvent.click(screen.getByText("Show the full quote"));
    expect(container.querySelector("blockquote")).toHaveTextContent(quote.trim());
  });

  it("an instant answer doesn't say 0.0 s", async () => {
    const { formatSeconds } = await import("./LatencyBadge");
    expect(formatSeconds(9)).toBe("under 0.1 s");
    expect(formatSeconds(6214)).toBe("6.2 s");
  });
});
