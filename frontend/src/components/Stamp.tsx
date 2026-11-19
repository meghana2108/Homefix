import type { Outcome } from "../state/steps";
import { Icon, OUTCOME_ICON } from "./Icons";

/** The outcome as a stamp: icon + words + colour, never colour alone. */
export function Stamp({ outcome, size = "md" }: { outcome: Outcome; size?: "sm" | "md" }) {
  const As = OUTCOME_ICON[outcome.icon] ?? OUTCOME_ICON.photo;
  return (
    <span className={`stamp stamp--${outcome.kind} ${size === "sm" ? "stamp--sm" : ""}`}>
      <Icon as={As} size={size === "sm" ? 14 : 16} className={outcome.kind === "working" ? "spin" : ""} />
      {outcome.label}
    </span>
  );
}
