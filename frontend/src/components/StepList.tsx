import { Check, CircleHelp, Loader2, OctagonAlert } from "lucide-react";
import type { Step } from "../state/steps";
import { Icon } from "./Icons";

const STATE_WORD = { running: "running", done: "done", stopped: "stopped", notfound: "no answer" } as const;
const MARK = { running: Loader2, done: Check, stopped: OctagonAlert, notfound: CircleHelp } as const;

/** What happened to the question, as a vertical sequence: each step, what it does, what it found. */
export function StepList({ steps, compact = false, label = "What happened to your question" }: {
  steps: Step[]; compact?: boolean; label?: string;
}) {
  if (steps.length === 0) return null;
  return (
    <ol className="steps" aria-label={label}>
      {steps.map((s, i) => (
        <li key={s.stage} className={`step step--${s.state}`}>
          {i < steps.length - 1 && <span className="step__line" aria-hidden="true" />}
          <span className="step__mark" aria-hidden="true">
            <Icon as={MARK[s.state]} size={14} className={s.state === "running" ? "spin" : ""} />
          </span>
          <div>
            <p className="step__title">
              <span>{s.title}<span className="sr-only">: {STATE_WORD[s.state]}</span></span>
              {s.stage === "loading_model" && s.ms != null && <span className="step__time">{(s.ms / 1000).toFixed(1)} s</span>}
            </p>
            {!compact && <p className="step__does">{s.does}</p>}
            {s.result && <p className="step__result">{s.result}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
