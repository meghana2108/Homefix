// Mirror of app/contracts.py. Same names, snake_case fields, null for Python None.
// tests/test_contract_sync.py fails if the literal lists or event field names differ.
export const STAGES = ["converting", "safety_check", "routing", "loading_model", "transcribing",
  "labeling_sounds", "extracting_frames", "retrieving", "generating", "verifying", "running_code"] as const;
export const REFUSAL_REASONS = ["safety", "unsupported_file", "empty_input", "too_large",
  "no_document", "not_in_document", "model_unavailable", "timeout"] as const;
export const EVENT_TYPES = ["status", "token", "transcript", "sound_labels", "frames", "citation",
  "code_result", "clarify", "refusal", "error", "final"] as const;
export type Stage = typeof STAGES[number];
export type RefusalReason = typeof REFUSAL_REASONS[number];
export type Modality = "image" | "audio" | "text" | "code" | "video" | "homefix" | "none";
export type QuestionType = "describe" | "count" | "read" | "qa" | "motion" | "speech" | "sound"
  | "doc_qa" | "code_gen" | "manual_lookup" | "none";
export type ProfileName = "full" | "lite";

export interface SoundLabel { label: string; score: number }

export interface StatusEvent {
  type: "status";
  stage: Stage;
  detail: string | null;
  ms: number | null;
}
export interface TokenEvent {
  type: "token";
  text: string;
}
export interface TranscriptEvent {
  type: "transcript";
  text: string;
  seconds: number;
}
export interface SoundLabelsEvent {
  type: "sound_labels";
  labels: SoundLabel[];
  is_speech: boolean;
}
export interface FramesEvent {
  type: "frames";
  timestamps: number[];
}
export interface CitationEvent {
  type: "citation";
  quote: string;
  page: number | null;
  source: string;
  score: number;
}
export interface CodeResultEvent {
  type: "code_result";
  code: string;
  passed: boolean;
  tests_run: number;
  failures: number;
  output_tail: string;
  attempts: number;
}
export interface ClarifyOption { label: string; message: string; manual_id: string | null }

/** HomeFix asks instead of guessing. final.answer repeats `question`. */
export interface ClarifyEvent {
  type: "clarify";
  question: string;
  seen: string | null;
  options: ClarifyOption[];
}

export interface RefusalEvent {
  type: "refusal";
  reason: RefusalReason;
  message: string;
  category: string | null;
}
export interface ErrorEvent {
  type: "error";
  stage: Stage;
  message: string;
  retryable: boolean;
}
export interface FinalEvent {
  type: "final";
  answer: string;
  modality: Modality;
  question_type: QuestionType;
  latency_ms: number;
  profile: ProfileName;
  model: string | null;
  /** "problem": the question is about something wrong (app/intent.py). */
  intent?: "problem" | "question" | null;
}
export type HomeFixEvent = StatusEvent | TokenEvent | TranscriptEvent | SoundLabelsEvent |
  FramesEvent | CitationEvent | CodeResultEvent | ClarifyEvent | RefusalEvent | ErrorEvent | FinalEvent;

export interface Manual { id: string; title: string; pages: number }
export interface WarmStep { name: string; label: string; state: "waiting" | "loading" | "ready" | "failed"; ms: number | null }

export interface Health {
  profile: ProfileName;
  ollama: boolean;
  models: Record<string, string>;
  loaded: string[];
  /** app/warmup.py: every model loads at API start; the app says "Getting ready" until done. */
  warm?: { ready: boolean; done: boolean; steps: WarmStep[] };
}

/** The header's words while models load: null when ready (or the server is too old to say). */
export function warmingText(h: Health | null): string | null {
  const w = h?.warm;
  if (!w || !w.steps.length) return null;
  const failed = w.steps.filter((s) => s.state === "failed");
  if (w.done) return failed.length ? `Couldn't load: ${failed.map((s) => s.label).join(", ")}` : null;
  const ready = w.steps.filter((s) => s.state === "ready").length;
  const now = w.steps.find((s) => s.state === "loading") ?? w.steps.find((s) => s.state === "waiting");
  return `Getting ready: ${now?.label ?? "models"} (${ready + 1} of ${w.steps.length})`;
}
