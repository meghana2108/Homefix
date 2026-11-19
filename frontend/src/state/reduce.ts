import type {
  CitationEvent,
  CodeResultEvent,
  ErrorEvent,
  FinalEvent,
  FramesEvent,
  HomeFixEvent,
  RefusalEvent,
  SoundLabelsEvent,
  Stage,
  TranscriptEvent,
} from "../contract";

export interface StatusChip {
  stage: Stage;
  detail: string | null;
  ms: number | null;
  done: boolean;
}

export type AttachmentKind = "image" | "audio" | "video" | "file";

/** What the user sent, kept so the conversation can show the photo, play the sound or the clip. */
export interface SentFile {
  name: string;
  kind: AttachmentKind;
  url: string | null;  // object URL for a preview; null in tests or for documents
}

export function kindOf(name: string, mime = ""): AttachmentKind {
  const ext = name.toLowerCase().split(".").pop() ?? "";
  if (mime.startsWith("image/") || ["jpg", "jpeg", "png", "webp", "gif", "heic", "heif"].includes(ext)) return "image";
  if (mime.startsWith("audio/") || ["wav", "mp3", "m4a", "ogg", "flac", "aac"].includes(ext)) return "audio";
  if (mime.startsWith("video/") || ["mp4", "mov", "webm", "m4v"].includes(ext)) return "video";
  return "file";
}

/** One question and everything streamed back for it. */
export interface Turn {
  id: string;
  userText: string;
  fileNames: string[];
  sentFiles: SentFile[];
  statuses: StatusChip[];
  answer: string;
  transcript: TranscriptEvent | null;
  soundLabels: SoundLabelsEvent | null;
  frames: FramesEvent | null;
  citation: CitationEvent | null;
  codeResult: CodeResultEvent | null;
  refusal: RefusalEvent | null;
  error: ErrorEvent | null;
  final: FinalEvent | null;
}

let counter = 0;

export function newTurn(userText: string, fileNames: string[], sentFiles?: SentFile[]): Turn {
  counter += 1;
  return {
    id: `t${Date.now().toString(36)}-${counter}`,
    userText,
    fileNames,
    sentFiles: sentFiles ?? fileNames.map((name) => ({ name, kind: kindOf(name), url: null })),
    statuses: [],
    answer: "",
    transcript: null,
    soundLabels: null,
    frames: null,
    citation: null,
    codeResult: null,
    refusal: null,
    error: null,
    final: null,
  };
}

/** Apply one event. Unknown event types return the same turn object (contract drift is ignored). */
export function reduce(turn: Turn, ev: HomeFixEvent | { type: string }): Turn {
  const e = ev as HomeFixEvent;
  switch (e.type) {
    case "status": {
      const last = turn.statuses[turn.statuses.length - 1];
      if (last && last.stage === e.stage) {
        const merged = { ...last, detail: e.detail ?? last.detail, ms: e.ms ?? last.ms };
        return { ...turn, statuses: [...turn.statuses.slice(0, -1), merged] };
      }
      const earlier = turn.statuses.map((s) => (s.done ? s : { ...s, done: true }));
      return { ...turn, statuses: [...earlier, { stage: e.stage, detail: e.detail, ms: e.ms, done: false }] };
    }
    case "token":
      return { ...turn, answer: turn.answer + e.text };
    case "transcript":
      return { ...turn, transcript: e };
    case "sound_labels":
      return { ...turn, soundLabels: e };
    case "frames":
      return { ...turn, frames: e };
    case "citation":
      return { ...turn, citation: e };
    case "code_result":
      return { ...turn, codeResult: e };
    case "refusal":
      return { ...turn, refusal: e };
    case "error":
      return { ...turn, error: e };
    case "final":
      return {
        ...turn,
        final: e,
        // final.answer is the full text (e.g. a count with the number put first); keep tokens if it's empty
        answer: e.answer || turn.answer,
        statuses: turn.statuses.map((s) => (s.done ? s : { ...s, done: true })),
      };
    default:
      return turn;
  }
}
