import type { StatusChip } from "../state/reduce";
import { formatSeconds } from "./LatencyBadge";

/** What each pipeline step means, in words a renter would use. */
export const LABELS: Record<string, string> = {
  converting: "Opening your files",
  safety_check: "Checking for danger",
  routing: "Choosing how to answer",
  loading_model: "Waking up the model",
  transcribing: "Listening to the recording",
  labeling_sounds: "Listening for sounds",
  extracting_frames: "Watching the video",
  retrieving: "Searching the manual",
  generating: "Writing the answer",
  verifying: "Checking the quote against the manual",
  running_code: "Testing the code",
};

/** Every step, with its detail and the model swap time. Shown under "How I got this". */
export function StatusChips({ statuses }: { statuses: StatusChip[] }) {
  if (statuses.length === 0) return null;
  return (
    <ol className="steps" aria-label="Steps">
      {statuses.map((s, i) => (
        <li key={`${s.stage}-${i}`} className={`step ${s.done ? "step--done" : "step--active"}`}>
          {s.done ? <span className="step__mark" aria-label="done">✓</span> : <span className="spinner" aria-label="running" />}
          <span>{LABELS[s.stage] ?? s.stage}</span>
          {s.detail && <span className="step__detail">· {s.detail}</span>}
          {s.stage === "loading_model" && s.ms != null && <span className="step__detail">· {formatSeconds(s.ms)}</span>}
        </li>
      ))}
    </ol>
  );
}
