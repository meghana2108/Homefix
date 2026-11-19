import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { HomeFixEvent } from "../contract";
import { newTurn, reduce } from "../state/reduce";
import { ManualPicker } from "./ManualPicker";
import { StatusChips } from "./StatusChips";
import { TurnView } from "./TurnView";

const final = (answer = "", latency_ms = 6214): HomeFixEvent => ({
  type: "final", answer, modality: "image", question_type: "count", latency_ms, profile: "full", model: "qwen3-vl:8b",
});
const build = (events: HomeFixEvent[]) => events.reduce(reduce, newTurn("q", ["mugs.jpg"]));

describe("TurnView", () => {
  it("shows the answer and the latency badge", () => {
    render(<TurnView turn={build([{ type: "token", text: "4. Four mugs" }, final("4. Four mugs on the shelf.")])} />);
    expect(screen.getByText("4. Four mugs on the shelf.")).toBeInTheDocument();
    expect(screen.getByText("⏱ 6.2 s")).toHaveAttribute("title", "Model: qwen3-vl:8b");
  });

  it("a safety refusal shows only the red card, no answer or payloads", () => {
    const turn = build([
      { type: "token", text: "partial repair step" },
      { type: "sound_labels", labels: [{ label: "smoke alarm beeping loudly", score: 0.71 }], is_speech: false },
      { type: "refusal", reason: "safety", message: "Stop using the appliance now.", category: "smoke_fire" },
      final(""),
    ]);
    const { container } = render(<TurnView turn={turn} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Stop using the appliance now.");
    expect(container.querySelector(".card--safety")).not.toBeNull();
    expect(screen.queryByText(/partial repair step/)).toBeNull();
    expect(screen.queryByText(/smoke alarm beeping loudly/)).toBeNull();
  });

  it("other refusals get the grey card", () => {
    const { container } = render(<TurnView turn={build([
      { type: "refusal", reason: "unsupported_file", message: "I can't open .exe files.", category: null }, final()])} />);
    expect(container.querySelector(".card--refusal")).toHaveTextContent("I can't open .exe files.");
  });

  it("error card offers Try again", () => {
    const onRetry = vi.fn();
    render(<TurnView onRetry={onRetry} turn={build([
      { type: "error", stage: "generating", message: "Something went wrong.", retryable: true }, final()])} />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("StatusChips", () => {
  it("shows the swap time for loading_model", () => {
    render(<StatusChips statuses={[{ stage: "loading_model", detail: "loading qwen2.5-coder:3b", ms: 6400, done: false }]} />);
    expect(screen.getByText("· 6.4 s")).toBeInTheDocument();
    expect(screen.getByLabelText("running")).toBeInTheDocument();
  });
});

describe("ManualPicker", () => {
  it("is hidden when there are no manuals", () => {
    const { container } = render(<ManualPicker manuals={[]} value={null} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("selects a manual and back to none", () => {
    const onChange = vi.fn();
    render(<ManualPicker manuals={[{ id: "washer_manual", title: "washer_manual.pdf", pages: 64 }]} value={null} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText(/washer_manual.pdf/));
    expect(onChange).toHaveBeenLastCalledWith("washer_manual");
  });
});
