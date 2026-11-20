import { describe, expect, it } from "vitest";
import type { HomeFixEvent } from "../contract";
import { buildEvidence, sha256 } from "./evidence";
import { newTurn, reduce } from "./reduce";

const turnOf = (q: string, files: string[], events: object[]) =>
  (events as HomeFixEvent[]).reduce(reduce, newTurn(q, files));
const FINAL = { type: "final", answer: "", modality: "text", question_type: "doc_qa", latency_ms: 1, profile: "lite", model: "m" };
const NOW = new Date("2026-11-19T23:40:00Z");

describe("evidence pack", () => {
  it("fingerprints a file with SHA-256 (known value)", async () => {
    expect(await sha256("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });

  it("puts the files' fingerprints, the verified quote and the danger check in the pack and the letter", async () => {
    const t = turnOf("Is mold my landlord's job?", ["lease.pdf"], [
      { type: "token", text: "The landlord fixes leaks within 7 days." },
      { type: "citation", quote: "Landlord repairs leaks within 7 days of notice.", page: 2, source: "lease.pdf", score: 100 },
      FINAL,
    ]);
    const e = await buildEvidence(t, [new File(["abc"], "lease.pdf", { type: "application/pdf" })], NOW);
    expect(e.files).toEqual([{ name: "lease.pdf", kind: "document", bytes: 3,
      sha256: "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" }]);
    expect(e.quote).toEqual({ text: "Landlord repairs leaks within 7 days of notice.", page: 2, source: "lease.pdf" });
    expect(e.danger).toMatch(/nothing dangerous/);
    expect(e.letter).toContain('My lease, page 2, says: "Landlord repairs leaks within 7 days of notice."');
    expect(e.letter).toContain("I've attached 1 file. Its SHA-256 fingerprint is in this request");
    expect(e.letter).not.toContain("What I found");  // the quote says it; no repeat
    expect(e.fingerprint).toMatch(/^[0-9a-f]{64}$/);
  });

  it("without a quote, the letter says what HomeFix found, and names a non-lease document plainly", async () => {
    const t = turnOf("Is the burner on?", [], [{ type: "token", text: "Yes, it is glowing red." }, FINAL]);
    expect((await buildEvidence(t, [], NOW)).letter).toContain("What I found: Yes, it is glowing red.");
    const g = turnOf("E21?", [], [{ type: "citation", quote: "E21 - cannot drain.", page: 2, source: "guide.pdf", score: 100 }, FINAL]);
    expect((await buildEvidence(g, [], NOW)).letter).toContain('The document "guide.pdf", page 2, says: "E21 - cannot drain."');
  });

  it("any change to the pack changes its fingerprint", async () => {
    const a = turnOf("q", [], [{ type: "token", text: "one" }, FINAL]);
    const b = turnOf("q", [], [{ type: "token", text: "two" }, FINAL]);
    expect((await buildEvidence(a, [], NOW)).fingerprint).not.toBe((await buildEvidence(b, [], NOW)).fingerprint);
    expect((await buildEvidence(a, [], NOW)).fingerprint).toBe((await buildEvidence(a, [], NOW)).fingerprint);
  });

  it("a danger stop is recorded as such, with no repair steps", async () => {
    const t = turnOf("I smell gas", [], [
      { type: "refusal", reason: "safety", message: "Leave now and call from outside.", category: "gas" }, FINAL]);
    const e = await buildEvidence(t, [], NOW);
    expect(e.danger).toMatch(/^Danger reported \(gas\)/);
    expect(e.found).toBe("Stopped by the danger check.");
  });

  it("when HomeFix asked back, the pack records what it read", async () => {
    const t = turnOf("What is this?", ["stove.jpg"], [
      { type: "clarify", question: "What would you like to know?", seen: "8:32\nCOOKTOP ON", options: [] }, FINAL]);
    expect((await buildEvidence(t, [], NOW)).found).toBe("HomeFix read: 8:32, COOKTOP ON.");
  });
});
