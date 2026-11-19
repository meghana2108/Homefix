import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TranscriptBlock } from "./TranscriptBlock";

describe("TranscriptBlock", () => {
  it("shows the transcript as a quote with its length", () => {
    const { container } = render(<TranscriptBlock transcript={{ type: "transcript", text: "The washer shows E21.", seconds: 8.1 }} />);
    expect(container.querySelector("blockquote")).toHaveTextContent("The washer shows E21.");
    expect(screen.getByText(/Transcript · 8\.1 s/)).toBeInTheDocument();
  });

  it("says when nothing was heard", () => {
    render(<TranscriptBlock transcript={{ type: "transcript", text: "", seconds: 2 }} />);
    expect(screen.getByText("(no words heard)")).toBeInTheDocument();
  });
});
