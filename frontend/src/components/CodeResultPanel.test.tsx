import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CodeResultPanel } from "./CodeResultPanel";

const base = { type: "code_result" as const, code: "def f():\n    return 1", passed: true, tests_run: 2,
  failures: 0, output_tail: "OK", attempts: 1 };

describe("CodeResultPanel", () => {
  it("shows a passed badge, attempt and code", () => {
    const { container } = render(<CodeResultPanel result={base} />);
    expect(screen.getByText("✓ passed 2/2")).toBeInTheDocument();
    expect(screen.getByText("Attempt 1 of 2")).toBeInTheDocument();
    expect(container.querySelector("pre code")).toHaveTextContent("return 1");
  });

  it("shows a failed badge and test output in details", () => {
    const { container } = render(<CodeResultPanel result={{ ...base, passed: false, tests_run: 3, failures: 1, output_tail: "boom", attempts: 2 }} />);
    expect(screen.getByText("✕ failed 1/3")).toBeInTheDocument();
    expect(screen.getByText("Test output")).toBeInTheDocument();
    expect(container.querySelector("details")).toHaveTextContent("boom");
  });

  it("says when no examples ran", () => {
    render(<CodeResultPanel result={{ ...base, passed: false, tests_run: 0, failures: 0 }} />);
    expect(screen.getByText("✕ no examples ran")).toBeInTheDocument();
  });

  it("scrolls long code inside the card", () => {
    const { container } = render(<CodeResultPanel result={{ ...base, code: "x = " + "a".repeat(500) }} />);
    expect(container.querySelector("pre")).toHaveStyle({ overflowX: "auto" });
    expect(container.querySelectorAll("pre")[1]).toHaveStyle({ overflowX: "auto" });
  });

  it("says (no output) when output_tail is empty", () => {
    render(<CodeResultPanel result={{ ...base, output_tail: "" }} />);
    expect(screen.getByText("(no output)")).toBeInTheDocument();
  });
});
