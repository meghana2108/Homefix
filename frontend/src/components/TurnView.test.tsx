import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { HomeFixEvent } from "../contract";
import { newTurn, reduce } from "../state/reduce";
import { ManualPicker } from "./ManualPicker";
import { StepList } from "./StepList";
import { TurnView } from "./TurnView";

const final = (answer = "", latency_ms = 6214): HomeFixEvent => ({
  type: "final", answer, modality: "image", question_type: "count", latency_ms, profile: "full", model: "qwen3-vl:8b",
});
const build = (events: HomeFixEvent[]) => events.reduce(reduce, newTurn("q", ["mugs.jpg"]));

describe("TurnView", () => {
  it("shows the answer and the latency badge", () => {
    render(<TurnView turn={build([{ type: "token", text: "4. Four mugs" }, final("4. Four mugs on the shelf.")])} />);
    expect(screen.getByText("4. Four mugs on the shelf.")).toBeInTheDocument();
    expect(screen.getByText("6.2 s")).toHaveAttribute("title", "Model: qwen3-vl:8b");
    expect(screen.getByText("Answered from your photo")).toBeInTheDocument();  // the outcome stamp
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

  it("other refusals get the amber card", () => {
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

describe("StepList", () => {
  it("shows the swap time for loading_model and says which step is running", () => {
    render(<StepList steps={[{ stage: "loading_model", title: "Load the model", does: "Loads it.", state: "running", result: null, ms: 6400 }]} />);
    expect(screen.getByText("6.4 s")).toBeInTheDocument();
    expect(screen.getByText(": running")).toBeInTheDocument();
  });
});

describe("ManualPicker", () => {
  it("is hidden when there are no manuals", () => {
    const { container } = render(<ManualPicker manuals={[]} value={null} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("offers automatic, each manual and none", () => {
    const onChange = vi.fn();
    render(<ManualPicker manuals={[{ id: "washer_manual", title: "Washer manual", pages: 64 }]} value="auto" onChange={onChange} />);
    const select = screen.getByLabelText("Manual");
    expect(select).toHaveValue("auto");
    fireEvent.change(select, { target: { value: "washer_manual" } });
    expect(onChange).toHaveBeenLastCalledWith("washer_manual");
    fireEvent.change(select, { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});
