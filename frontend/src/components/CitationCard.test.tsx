import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CitationCard } from "./CitationCard";

const base = { type: "citation" as const, quote: "Clean the filter monthly.", page: 37, source: "washer_manual.pdf", score: 95 };

describe("CitationCard", () => {
  it("shows the quote, page and source", () => {
    const { container } = render(<CitationCard citation={base} />);
    expect(container.querySelector("blockquote")).toHaveTextContent("Clean the filter monthly.");
    expect(screen.getByText("p. 37 · washer_manual.pdf")).toBeInTheDocument();
  });

  it("shows only the source when page is null", () => {
    render(<CitationCard citation={{ ...base, page: null }} />);
    expect(screen.getByText("washer_manual.pdf")).toBeInTheDocument();
    expect(screen.queryByText(/p\./)).toBeNull();
  });

  it("wraps long unbroken quotes", () => {
    const { container } = render(<CitationCard citation={base} />);
    expect(container.querySelector("blockquote")).toHaveStyle({ overflowWrap: "anywhere" });
  });
});
