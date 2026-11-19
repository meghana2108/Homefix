import type { StatusChip } from "../state/reduce";
import { formatSeconds } from "./LatencyBadge";

const LABELS: Record<string, string> = {
  converting: "converting",
  safety_check: "safety check",
  routing: "routing",
  loading_model: "loading model",
  transcribing: "transcribing",
  labeling_sounds: "labeling sounds",
  extracting_frames: "extracting frames",
  retrieving: "searching the document",
  generating: "generating",
  verifying: "checking the quote",
  running_code: "running the code",
};

export function StatusChips({ statuses }: { statuses: StatusChip[] }) {
  if (statuses.length === 0) return null;
  return (
    <ol className="chips" aria-label="Steps">
      {statuses.map((s, i) => (
        <li key={`${s.stage}-${i}`} className={`chip ${s.done ? "chip--done" : "chip--active"}`}>
          {s.done ? <span aria-label="done">✓</span> : <span className="spinner" aria-label="running" />}
          <span>{LABELS[s.stage] ?? s.stage}</span>
          {s.detail && <span className="chip__detail">· {s.detail}</span>}
          {s.stage === "loading_model" && s.ms != null && <span className="chip__detail">· {formatSeconds(s.ms)}</span>}
        </li>
      ))}
    </ol>
  );
}
