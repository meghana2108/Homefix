import type { Turn } from "./reduce";

/** A repair request the renter can print or save: what they sent (with SHA-256 fingerprints), what HomeFix
 *  found, the verified quote, and the danger check. Made in the browser, offline; nothing is uploaded. */
export interface EvidenceFile { name: string; kind: string; bytes: number; sha256: string }
export interface Evidence {
  madeAt: string;            // local date and time, e.g. "19 Nov 2026, 23:40"
  madeAtIso: string;
  question: string;
  files: EvidenceFile[];
  found: string;             // HomeFix's answer, or what it read when it asked back
  quote: { text: string; page: number | null; source: string } | null;
  danger: string;            // the danger check, in words
  letter: string;
  fingerprint: string;       // SHA-256 of everything above, so a changed pack doesn't match
}

const hex = (buf: ArrayBuffer) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");

function bytesOf(file: Blob): Promise<ArrayBuffer> {
  if (typeof file.arrayBuffer === "function") return file.arrayBuffer();
  return new Promise((ok, fail) => {
    const r = new FileReader();
    r.onload = () => ok(r.result as ArrayBuffer);
    r.onerror = () => fail(r.error);
    r.readAsArrayBuffer(file);
  });
}

/** SHA-256 in hex, or "" where the browser has no Web Crypto (plain http on another device). */
export async function sha256(data: Blob | string): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return "";
  const buf = typeof data === "string" ? new TextEncoder().encode(data) : new Uint8Array(await bytesOf(data));
  return hex(await subtle.digest("SHA-256", buf));
}

const KIND: Record<string, string> = { image: "photo", audio: "recording", video: "clip", file: "document" };

export function dangerText(turn: Turn): string {
  if (turn.refusal?.reason === "safety") return `Danger reported (${turn.refusal.category ?? "safety"}). HomeFix gave no repair steps: ${turn.refusal.message}`;
  return "Checked first: nothing dangerous in the question.";
}

export function foundText(turn: Turn): string {
  if (turn.refusal?.reason === "safety") return "Stopped by the danger check.";
  if (turn.clarify) return turn.clarify.seen ? `HomeFix read: ${turn.clarify.seen.split("\n").join(", ")}.` : turn.clarify.question;
  if (turn.refusal) return turn.refusal.message;
  if (turn.soundLabels?.labels.length) {
    return `Sounds most like: ${turn.soundLabels.labels.slice(0, 3).map((l) => `${l.label} (${Math.round(l.score * 100)}%)`).join(", ")}. ${turn.answer}`.trim();
  }
  return turn.answer.trim();
}

export function draftLetter(e: Omit<Evidence, "letter" | "fingerprint">): string {
  const lines = ["Dear landlord,", "", `I'm writing on ${e.madeAt} to report a problem in my unit.`];
  if (e.question) lines.push(`The problem: ${e.question}`);
  if (e.quote) {
    // a verified quote says it better than our summary of it
    const doc = /lease/i.test(e.quote.source) ? "My lease" : `The document "${e.quote.source}"`;
    lines.push(`${doc}${e.quote.page != null ? `, page ${e.quote.page},` : ""} says: "${e.quote.text}"`);
  } else if (e.found) {
    lines.push(`What I found: ${e.found}`);
  }
  if (e.files.length) {
    lines.push(e.files.length === 1
      ? "I've attached 1 file. Its SHA-256 fingerprint is in this request, so you can check it hasn't been changed."
      : `I've attached ${e.files.length} files. Their SHA-256 fingerprints are in this request, so you can check they haven't been changed.`);
  }
  lines.push("", "Please let me know when this can be fixed.", "", "Thank you,");
  return lines.join("\n");
}

export async function buildEvidence(turn: Turn, files: File[], now = new Date()): Promise<Evidence> {
  const fileRows: EvidenceFile[] = [];
  for (const f of files) {
    const kind = turn.sentFiles.find((s) => s.name === f.name)?.kind ?? "file";
    fileRows.push({ name: f.name, kind: KIND[kind] ?? kind, bytes: f.size, sha256: await sha256(f) });
  }
  const c = turn.citation;
  const base = {
    madeAt: now.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }),
    madeAtIso: now.toISOString(),
    question: turn.userText,
    files: fileRows,
    found: foundText(turn),
    quote: c ? { text: c.quote, page: c.page, source: c.source } : null,
    danger: dangerText(turn),
  };
  const letter = draftLetter(base);
  const fingerprint = await sha256(JSON.stringify({ ...base, letter }));
  return { ...base, letter, fingerprint };
}

export type FileCheck =
  | { ok: true; name: string; sha256: string; match: EvidenceFile }
  | { ok: false; name: string; sha256: string; sameName: EvidenceFile | null };

/** Is this file one of the files in the request, byte for byte? */
export async function checkFile(file: File, files: EvidenceFile[]): Promise<FileCheck> {
  const hash = await sha256(file);
  const match = files.find((f) => f.sha256 && f.sha256 === hash);
  if (match) return { ok: true, name: file.name, sha256: hash, match };
  return { ok: false, name: file.name, sha256: hash, sameName: files.find((f) => f.name === file.name) ?? null };
}

/** Words that mean "this isn't yours to fix": the answer or the manual says to get the landlord or a pro. */
const NEEDS_HELP = new RegExp(
  "\\b(call|contact|tell|ask|notify|report (it )?to|have|get)\\b[^.]{0,60}\\b(maintenance|landlord|property manager|" +
  "building manager|superintendent|super|plumber|electrician|technician|professional|repair (person|service)|" +
  "service (center|technician)|gas company|utility)\\b|\\b(licensed|qualified) (electrician|plumber|technician|professional)\\b",
  "i");

/** Words that make a question about a problem, not just a question ("Is it heating or cooling?"). */
const PROBLEM = new RegExp(
  "\\b(broken|break(s|ing)?|not working|(does|is|are|do|did|was)n'?t (work|drain|turn|start|heat|cool|close|open|flush|stop)|" +
  "won'?t|stopped|leak\\w*|drip\\w*|flood\\w*|overflow\\w*|mou?ld\\w*|damp|smell\\w*|odou?r|noise|noisy|loud|" +
  "beep\\w*|chirp\\w*|alarm\\w*|error|code|fault\\w*|flash\\w*|blink\\w*|problem|issue|wrong|fix|repair\\w*|" +
  "damage\\w*|crack\\w*|clog\\w*|block\\w*|jam\\w*|trip\\w*|spark\\w*|burn\\w*|stuck|no (heat|hot water|power|water)|" +
  "too (hot|cold)|freez\\w*|ice|pest\\w*|roach\\w*|mice|mouse|rats?|bugs?)\\b",
  "i");

export type Escalation = "suggest" | "optional" | "none";

/** Whether to offer a repair request for this answer. Never by default (D15):
 *  - suggested only after a danger stop, or when the answer or the quoted manual says to get the landlord or
 *    a professional;
 *  - a quiet link, the renter's choice, only when the question is about a problem (leak, error code, won't
 *    drain);
 *  - nothing for a plain question ("Is it heating or cooling?", "Can I have a cat?"). */
export function escalation(turn: Turn): Escalation {
  if (!turn.final || turn.error || turn.clarify || turn.codeResult) return "none";
  if (turn.refusal?.reason === "safety") return "suggest";
  if (NEEDS_HELP.test(`${turn.answer} ${turn.citation?.quote ?? ""}`)) return "suggest";
  // the server judges by meaning too (app/intent.py); the word list is the fallback (mock server, older API)
  const problem = turn.final.intent ? turn.final.intent === "problem" : PROBLEM.test(turn.userText);
  return problem ? "optional" : "none";
}
