import { readFileSync } from "node:fs";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RefusalCard } from "./RefusalCard";

const css = readFileSync("src/index.css", "utf8");
const root = css.match(/:root\s*\{[^}]*\}/)![0];

describe("maintenance-tag theme", () => {
  it("tokens match the maintenance-tag palette", () => {
    const want: Record<string, string> = {
      paper: "#f4f2ee", wash: "#f0ece5", ink: "#1c1917", "ink-soft": "#44403c", "ink-faint": "#6b645f",
      rule: "#e2ddd4", "rule-strong": "#b8b0a3", pen: "#c2410c", "pen-deep": "#9a3412", "pen-tint": "#fdeee4",
      panel: "#1f1d1b", seg: "#ff8a3d", "seg-dim": "#5a3a26", hazard: "#f5b800",
      sheet: "#ffffff", answered: "#0b6b5e", notfound: "#7d4a00", danger: "#b3261e",
    };
    for (const [name, hex] of Object.entries(want)) expect(root).toContain(`--${name}: ${hex};`);
  });

  it("the landing card and the demo page each own one root rule", () => {
    expect(css.match(/^\.demo\s*\{/gm)).toHaveLength(1);
    expect(css.match(/^\.demo-page\s*\{/gm)).toHaveLength(1);
  });

  it("no raw hex outside :root", () => {
    const rest = css.replace(root, "");
    const hits = (rest.match(/#[0-9a-fA-F]{3,6}\b/g) ?? []).filter((h) => !["#fff", "#000"].includes(h.toLowerCase()));
    expect(hits).toEqual([]);
  });

  it("safety card has a hazard stripe", () => {
    const { container } = render(<RefusalCard refusal={{ type: "refusal", category: null, reason: "safety", message: "Stop. Leave and call 911." }} />);
    expect(container.querySelector(".card--safety .hazard")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("not-in-document card has no stripe", () => {
    const { container } = render(<RefusalCard refusal={{ type: "refusal", category: null, reason: "not_in_document", message: "Not there." }} />);
    expect(container.querySelector(".hazard")).toBeNull();
  });
});
