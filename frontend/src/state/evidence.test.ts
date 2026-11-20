import { describe, expect, it } from "vitest";
import type { HomeFixEvent } from "../contract";
import { buildEvidence, escalation, sha256 } from "./evidence";
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

  it("suggests escalating only when the answer says it needs your landlord or a professional", () => {
    const ans = (text: string, extra: object[] = []) => turnOf("What does this mean?", [], [{ type: "token", text }, ...extra, FINAL]);
    expect(escalation(ans("If it trips again, leave it off and call the maintenance line."))).toBe("suggest");
    expect(escalation(ans("The battery is low. Tell maintenance."))).toBe("suggest");
    expect(escalation(ans("Have a licensed electrician check the outlet."))).toBe("suggest");
    // the manual's quote can say it even when the short answer doesn't
    expect(escalation(ans("Clean the filter.", [
      { type: "citation", quote: "If E21 comes back after cleaning the filter, call the maintenance line.", page: 2, source: "g.pdf", score: 100 },
    ]))).toBe("suggest");
    expect(escalation(turnOf("I smell gas", [], [
      { type: "refusal", reason: "safety", message: "Leave now.", category: "gas" }, FINAL]))).toBe("suggest");
  });

  it("a question about a problem gets the quiet link; a plain question gets nothing", () => {
    const q = (question: string, text: string) => turnOf(question, [], [{ type: "token", text }, FINAL]);
    // problems: escalating is the renter's choice
    expect(escalation(q("My dishwasher won't drain", "Clean the filter in the bottom of the tub."))).toBe("optional");
    expect(escalation(q("There's mold in my bathroom", "Scrub it with detergent and water."))).toBe("optional");
    expect(escalation(q("My washer shows this code. What should I do?", "E21 means it can't drain."))).toBe("optional");
    expect(escalation(q("The kitchen tap is dripping", "Turn the handle fully off."))).toBe("optional");
    // just questions: nothing to escalate
    expect(escalation(q("Is it heating or cooling?", "Cool"))).toBe("none");
    expect(escalation(q("What temperature is the thermostat set to?", "The thermostat is set to 68°F."))).toBe("none");
    expect(escalation(q("Can I have a cat?", "Yes, with a $300 pet deposit."))).toBe("none");
    expect(escalation(q("How much notice do I need to give before I move out?", "60 days, in writing."))).toBe("none");
  });

  it("never offers it while answering, after an error, when HomeFix asked back, or for code", () => {
    expect(escalation(newTurn("q", []))).toBe("none");
    expect(escalation(turnOf("q", [], [{ type: "error", stage: "generating", message: "x", retryable: true }, FINAL]))).toBe("none");
    expect(escalation(turnOf("q", [], [{ type: "clarify", question: "Which appliance?", seen: null, options: [] }, FINAL]))).toBe("none");
    expect(escalation(turnOf("q", [], [{ type: "code_result", code: "def f(): pass", passed: true, tests_run: 1,
      failures: 0, output_tail: "", attempts: 1 }, FINAL]))).toBe("none");
  });

  it("uses the server's judgment of the question when it has one (meaning, not just words)", () => {
    const withIntent = (q: string, intent: "problem" | "question") =>
      turnOf(q, [], [{ type: "token", text: "ok" }, { ...FINAL, intent }]);
    expect(escalation(withIntent("the fridge sounds weird", "problem"))).toBe("optional");  // no problem word
    expect(escalation(withIntent("Is it heating or cooling?", "question"))).toBe("none");
  });
});
