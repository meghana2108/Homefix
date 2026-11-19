import type { RefusalEvent } from "../contract";

/** A plain title for each kind of "no", so the user knows what happened and what to do next. */
const TITLES: Record<string, string> = {
  not_in_document: "Not in the document",
  no_document: "Give me something to answer from",
  unsupported_file: "Can't open that file",
  empty_input: "Nothing to answer yet",
  too_large: "That file is too big",
  model_unavailable: "The local model isn't ready",
  timeout: "That took too long",
};

/** The fixed safety message as steps: its opening line repeats the card title, so it is dropped. */
export function safetySteps(message: string): string[] {
  const body = message.replace(/^\s*⚠️?\s*This could be dangerous\.\s*/i, "");
  return body.split(/(?<=[.!])\s+(?=[A-Z])/).map((x) => x.trim()).filter(Boolean);
}

export function RefusalCard({ refusal }: { refusal: RefusalEvent }) {
  if (refusal.reason === "safety") {
    const steps = safetySteps(refusal.message);
    return (
      <div className="card card--safety" role="alert">
        <p className="card__title"><span aria-hidden="true">⚠️ </span>Stop: this could be dangerous</p>
        {steps.length > 1
          ? <ul className="safety__steps">{steps.map((x, i) => <li key={i}>{x}</li>)}</ul>
          : <p>{steps[0] ?? refusal.message}</p>}
      </div>
    );
  }
  return (
    <div className="card card--refusal" role="status">
      {TITLES[refusal.reason] && <p className="card__title">{TITLES[refusal.reason]}</p>}
      <p>{refusal.message}</p>
    </div>
  );
}
