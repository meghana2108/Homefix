import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FrameStrip } from "./FrameStrip";

const SIXTEEN = Array.from({ length: 16 }, (_, i) => Math.round(i * 1.873 * 10) / 10);

describe("FrameStrip", () => {
  it("renders one tick per timestamp", () => {
    const { container } = render(<FrameStrip timestamps={SIXTEEN} />);
    expect(container.querySelectorAll(".framestrip__tick")).toHaveLength(16);
    expect(screen.getByText("16 frames · 0.0–28.1 s")).toBeInTheDocument();
  });

  it("each tick is focusable and names its time", () => {
    render(<FrameStrip timestamps={[0, 1.94, 3.8]} />);
    const tick = screen.getByRole("button", { name: "Frame 2 at t=1.9s" });
    fireEvent.focus(tick);
    expect(screen.getByText("t=1.9s")).toBeInTheDocument();
  });

  it("places ticks along the clip", () => {
    const { container } = render(<FrameStrip timestamps={[0, 5, 10]} />);
    const ticks = container.querySelectorAll<HTMLElement>(".framestrip__tick");
    expect([...ticks].map((t) => t.style.left)).toEqual(["0%", "50%", "100%"]);
  });

  it("handles a single frame and no frames", () => {
    const { container, rerender } = render(<FrameStrip timestamps={[2]} />);
    expect(container.querySelectorAll(".framestrip__tick")).toHaveLength(1);
    expect(screen.getByText("1 frame · 2.0 s")).toBeInTheDocument();
    rerender(<FrameStrip timestamps={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
