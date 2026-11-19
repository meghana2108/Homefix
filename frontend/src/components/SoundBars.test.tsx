import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SoundBars } from "./SoundBars";

const LABELS = [
  { label: "washing machine beeping", score: 0.71 },
  { label: "beep, bleep", score: 0.12 },
  { label: "alarm", score: 0.05 },
];

describe("SoundBars", () => {
  it("renders 3 bars with whole percents, highest first", () => {
    const { container } = render(<SoundBars labels={LABELS} />);
    expect(screen.getByText("71%")).toBeInTheDocument();
    expect(screen.getByText("washing machine beeping")).toBeInTheDocument();
    const bars = container.querySelectorAll(".soundbar__fill");
    expect(bars).toHaveLength(3);
    expect((bars[0] as HTMLElement).style.width).toBe("71%");
  });

  it("is a list a screen reader can read (text, not colour alone)", () => {
    render(<SoundBars labels={LABELS} />);
    expect(screen.getByRole("list", { name: "Sounds heard" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")[2]).toHaveTextContent("alarm5%");
  });

  it("keeps a tiny score visible and clamps bad ones", () => {
    const { container } = render(<SoundBars labels={[{ label: "x", score: 0.001 }, { label: "y", score: 1.7 }]} />);
    const bars = container.querySelectorAll<HTMLElement>(".soundbar__fill");
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(bars[0].style.width).toBe("1%");
    expect(bars[1].style.width).toBe("100%");
  });

  it("renders nothing for an empty list", () => {
    const { container } = render(<SoundBars labels={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
