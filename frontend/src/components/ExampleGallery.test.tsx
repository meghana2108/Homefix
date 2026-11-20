import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EXAMPLE_KINDS, EXAMPLES, ordered } from "../examples";
import { ExampleGallery } from "./ExampleGallery";

describe("example gallery", () => {
  it("every capability has at least two examples, and make_samples.py writes every sample file", () => {
    for (const k of EXAMPLE_KINDS) expect(EXAMPLES.filter((e) => e.kind === k.id).length).toBeGreaterThanOrEqual(2);
    // The samples are generated, not in git (hard rule test bans .wav/.mp4/.pdf), so check the script names each one.
    const scripts = ["make_samples.py", "fetch_real_samples.py"]
      .map((f) => readFileSync(resolve(__dirname, "../../../scripts", f), "utf8")).join("\n");
    for (const e of EXAMPLES.filter((x) => x.file)) expect(scripts, e.file).toContain(`"${e.file}"`);
    expect(new Set(EXAMPLES.map((e) => e.id)).size).toBe(EXAMPLES.length);
  });

  it("every example says where its file came from; real ones name the author and license", () => {
    for (const e of EXAMPLES.filter((x) => x.file)) {
      expect(e.source, e.id).toBeDefined();
      if (e.source!.real) expect(e.source!.credit, e.id).toMatch(/CC0|CC BY|Public domain/);
    }
    // every example says what kind it is
    for (const e of EXAMPLES) expect(["fix", "question", "asks", "stop"], e.id).toContain(e.role);
  });

  it("each tab leads with problems and their fixes, then questions, then the ones that ask back", () => {
    const rank = { stop: 0, fix: 0, question: 1, asks: 2 } as const;
    for (const k of EXAMPLE_KINDS) {
      const shown = ordered(k.id).map((e) => [rank[e.role], e.source?.real === false ? 1 : 0]);
      const sorted = [...shown].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      expect(shown, k.id).toEqual(sorted);
    }
    for (const k of ["photo", "sound", "voice", "document", "manual"] as const) expect(ordered(k)[0].role, k).toBe("fix");
  });

  it("labels each card: problem and fix, question, or asks back", () => {
    render(<ExampleGallery onTry={() => {}} busy={false} manuals={[]} />);
    expect(screen.getAllByText("Problem → fix").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Asks you back").length).toBeGreaterThan(0);
    const first = screen.getAllByRole("listitem")[0];
    expect(first).toHaveTextContent("Problem → fix");
  });

  it("shows the credit under a real photo", () => {
    render(<ExampleGallery onTry={() => {}} busy={false} manuals={[]} />);
    expect(screen.getAllByText(/Real photo/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Drawn by us/).length).toBeGreaterThan(0);
  });

  it("switches tabs and sends the example on Try it", () => {
    const onTry = vi.fn();
    render(<ExampleGallery onTry={onTry} busy={false} manuals={[{ id: "g", title: "Unit 4B guide", pages: 4 }]} />);
    expect(screen.getByRole("tab", { name: "Photo" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "Document" }));
    fireEvent.click(screen.getByRole("button", { name: "Try it: Can I have a cat?" }));
    expect(onTry).toHaveBeenCalledWith(expect.objectContaining({ id: "D2", file: "lease_unit_4b.pdf" }));
    fireEvent.click(screen.getByRole("tab", { name: "Manual" }));
    expect(screen.getByText("Manuals HomeFix can read now")).toBeInTheDocument();
    expect(screen.getByText("Unit 4B guide")).toBeInTheDocument();
  });

  it("Try it waits while a question is running", () => {
    render(<ExampleGallery onTry={() => {}} busy manuals={[]} />);
    screen.getAllByRole("button", { name: /^Try it/ }).forEach((b) => expect(b).toBeDisabled());
  });
});
