import type { StatusChip } from "../state/reduce";
import { LABELS } from "./StatusChips";

/** The checks worth telling a user about once the answer is in. */
const TRUST: Record<string, string> = {
  safety_check: "Checked for danger",
  transcribing: "Transcribed on this laptop",
  labeling_sounds: "Sound matched on this laptop",
  retrieving: "Searched the manual",
  verifying: "Quote checked against the manual",
  running_code: "Code tested before showing it",
};

/** One live line while working ("Listening for sounds…"), then a short line of the checks that ran. */
export function Progress({ statuses, done }: { statuses: StatusChip[]; done: boolean }) {
  if (statuses.length === 0) {
    return done ? null : <p className="progress progress--live"><span className="spinner" aria-hidden="true" />Starting…</p>;
  }
  if (!done) {
    const current = statuses[statuses.length - 1];
    return (
      <p className="progress progress--live" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        {LABELS[current.stage] ?? current.stage}…
      </p>
    );
  }
  const seen = [...new Set(statuses.map((s) => s.stage))].filter((s) => TRUST[s]);
  if (seen.length === 0) return null;
  return (
    <p className="progress">
      {seen.map((s, i) => <span key={s} className="progress__item">{i > 0 && <span aria-hidden="true"> · </span>}✓ {TRUST[s]}</span>)}
    </p>
  );
}
