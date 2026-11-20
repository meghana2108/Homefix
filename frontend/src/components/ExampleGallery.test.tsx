import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EXAMPLE_KINDS, EXAMPLES } from "../examples";
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
    // the real ones come first in each tab
    for (const k of EXAMPLE_KINDS) {
      const files = EXAMPLES.filter((e) => e.kind === k.id && e.file);
      const firstMade = files.findIndex((e) => !e.source!.real);
      if (firstMade >= 0) expect(files.slice(firstMade).every((e) => !e.source!.real), k.id).toBe(true);
    }
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
