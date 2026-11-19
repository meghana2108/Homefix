import type { Stage } from "../contract";
import type { Turn } from "./reduce";

export type StepState = "running" | "done" | "stopped" | "notfound";

export interface Step {
  stage: Stage;
  title: string;
  /** What the step does, in the user's words. */
  does: string;
  state: StepState;
  /** What it found, from the real events of this turn. */
  result: string | null;
  ms: number | null;
}

export const STEP_TEXT: Record<Stage, { title: string; does: string }> = {
  converting: { title: "Open your files", does: "Turns photos, sounds and clips into a form the models can read." },
  safety_check: { title: "Check for danger", does: "Looks for gas, fire, smoke, sparks or water near power before anything else." },
  routing: { title: "Choose how to answer", does: "Picks the right part of HomeFix for what you sent." },
  loading_model: { title: "Load the model", does: "Loads the model into memory. Only the first question after a pause waits for this." },
  transcribing: { title: "Listen to the recording", does: "Turns speech into text, on this laptop." },
  labeling_sounds: { title: "Name the sound", does: "Compares the sound with hundreds of known household sounds." },
  extracting_frames: { title: "Watch the video", does: "Takes evenly spaced frames from the clip." },
  retrieving: { title: "Search the manual", does: "Finds the pages that match your question." },
  generating: { title: "Write the answer", does: "The local model answers from what you sent, and nothing else." },
  verifying: { title: "Check the quote", does: "Makes sure the quoted words are really in the document. No quote, no answer." },
  running_code: { title: "Test the code", does: "Runs the code's own examples in a sandbox before showing it." },
};

const ROUTE_WORDS: Record<string, string> = {
  image: "A question about your photo.",
  audio: "A sound or a voice note.",
  text: "An answer from the document.",
  video: "A question about your clip.",
  code: "Write a function and test it.",
  homefix: "Your photo, checked against the manual.",
};

/** Refusals the router itself gives (nothing to answer from, a file it can't open). */
const ROUTE_REFUSALS = new Set(["no_document", "empty_input", "unsupported_file", "too_large"]);

const pct = (s: number) => `${Math.round(s * 100)}%`;
const sec = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

function kinds(turn: Turn): string {
  const n = turn.sentFiles.length;
  if (n === 0) return "No files, just your question.";
  const count: Record<string, number> = {};
  for (const f of turn.sentFiles) count[f.kind] = (count[f.kind] ?? 0) + 1;
  const word = { image: "photo", audio: "recording", video: "clip", file: "document" } as const;
  return `${Object.entries(count).map(([k, c]) => `${c} ${word[k as keyof typeof word]}${c > 1 ? "s" : ""}`).join(", ")}, ready.`;
}

function resultFor(stage: Stage, turn: Turn, detail: string | null, ms: number | null, done: boolean): string | null {
  const { refusal, citation } = turn;
  switch (stage) {
    case "converting":
      return done ? kinds(turn) : null;
    case "safety_check":
      if (refusal?.reason === "safety") return "Signs of danger, so HomeFix stops here.";
      return done ? "Nothing dangerous in your words." : null;
    case "routing":
      if (detail) return `${detail}.`;
      if (refusal && ROUTE_REFUSALS.has(refusal.reason)) return refusal.message;
      return turn.final && ROUTE_WORDS[turn.final.modality] ? ROUTE_WORDS[turn.final.modality] : null;
    case "loading_model":
      return ms != null ? `Ready in ${sec(ms)}.` : null;
    case "transcribing":
      return turn.transcript ? `Heard ${turn.transcript.seconds.toFixed(1)} s of speech.` : null;
    case "labeling_sounds": {
      const top = turn.soundLabels?.labels[0];
      return top ? `Most likely ${top.label} (${pct(top.score)}).` : null;
    }
    case "extracting_frames": {
      const ts = turn.frames?.timestamps;
      if (!ts?.length) return detail === "cached" ? "Frames reused from before." : null;
      return `${ts.length} frames, ${Math.min(...ts).toFixed(1)} to ${Math.max(...ts).toFixed(1)} s.`;
    }
    case "retrieving":
      return citation ? `Searched ${citation.source}.` : done ? "Searched the document." : null;
    case "generating":
      if (detail && /^found\s/i.test(detail)) return `Read ${detail.replace(/^found\s+/i, "")} from the photo.`;
      return done && turn.final?.model ? `Answered by ${turn.final.model}, on this laptop.` : null;
    case "verifying":
      if (citation) return citation.page != null ? `Found word for word on page ${citation.page}.` : "Found word for word.";
      if (refusal?.reason === "not_in_document") return "No exact quote, so no answer.";
      return null;
    case "running_code": {
      const r = turn.codeResult;
      if (!r) return null;
      return r.passed ? `Passed ${r.tests_run - r.failures} of ${r.tests_run} examples.`
        : r.tests_run === 0 ? "No examples ran." : `Failed ${r.failures} of ${r.tests_run} examples.`;
    }
    default:
      return null;
  }
}

/** One step per stage seen, in order, with its state and what it found. */
export function stepsOf(turn: Turn): Step[] {
  const finished = turn.final !== null;
  const seen = new Map<Stage, { detail: string | null; ms: number | null; done: boolean }>();
  for (const s of turn.statuses) {
    const prev = seen.get(s.stage);
    seen.set(s.stage, { detail: s.detail ?? prev?.detail ?? null, ms: s.ms ?? prev?.ms ?? null, done: s.done || finished });
  }
  const steps: Step[] = [];
  for (const [stage, v] of seen) {
    const text = STEP_TEXT[stage] ?? { title: stage, does: "" };
    let state: StepState = v.done ? "done" : "running";
    if (stage === "safety_check" && turn.refusal?.reason === "safety") state = "stopped";
    if (stage === "verifying" && turn.refusal?.reason === "not_in_document") state = "notfound";
    if (stage === "routing" && turn.refusal && ROUTE_REFUSALS.has(turn.refusal.reason)) state = "notfound";
    steps.push({ stage, ...text, state, result: resultFor(stage, turn, v.detail, v.ms, v.done), ms: v.ms });
  }
  // a "not in the document" that came before any quote check: the last step says why there is no answer
  if (finished && turn.refusal?.reason === "not_in_document" && steps.length && !seen.has("verifying")) {
    steps[steps.length - 1] = { ...steps[steps.length - 1], state: "notfound", result: "No answer in the document." };
  }
  if (finished && turn.error && steps.length) steps[steps.length - 1] = { ...steps[steps.length - 1], state: "stopped", result: turn.error.message };
  return steps;
}

export type OutcomeKind = "answered" | "notfound" | "danger" | "info" | "working";
export interface Outcome { kind: OutcomeKind; label: string; icon: string }

/** The one-glance verdict on a turn, shown as a stamp above the answer. */
export function outcomeOf(turn: Turn): Outcome {
  const { refusal, error, citation, codeResult, final } = turn;
  if (refusal?.reason === "safety") return { kind: "danger", label: "Stop: this could be dangerous", icon: "danger" };
  if (!final) return { kind: "working", label: "Working on it", icon: "working" };
  if (error) return { kind: "danger", label: "Something went wrong", icon: "error" };
  if (refusal?.reason === "not_in_document") return { kind: "notfound", label: "Not in the document", icon: "notfound" };
  if (refusal) return { kind: "notfound", label: "Couldn't answer this one", icon: "notfound" };
  if (citation) {
    const where = turn.sentFiles.some((f) => f.kind === "file") ? "your document" : "the manual";
    return { kind: "answered", label: citation.page != null ? `From ${where}, page ${citation.page}` : `From ${where}`, icon: "cited" };
  }
  if (codeResult) return codeResult.passed
    ? { kind: "answered", label: `Code tested: passed ${codeResult.tests_run - codeResult.failures} of ${codeResult.tests_run}`, icon: "code" }
    : { kind: "notfound", label: "Code tested: it didn't pass", icon: "code" };
  if (turn.soundLabels) return { kind: "info", label: "Sound identified", icon: "sound" };
  if (turn.transcript) return { kind: "info", label: "Voice note transcribed", icon: "voice" };
  if (final.modality === "video") return { kind: "info", label: "Answered from your clip", icon: "video" };
  if (final.modality === "image") return { kind: "info", label: "Answered from your photo", icon: "photo" };
  return { kind: "info", label: "Answered", icon: "photo" };
}
