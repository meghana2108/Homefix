import type { Turn } from "../state/reduce";
import { outcomeOf, stepsOf, STEP_TEXT } from "../state/steps";
import { AnswerText } from "./AnswerText";
import { CitationCard } from "./CitationCard";
import { CodeResultPanel } from "./CodeResultPanel";
import { ErrorCard } from "./ErrorCard";
import { FrameStrip } from "./FrameStrip";
import { LatencyBadge } from "./LatencyBadge";
import { RefusalCard } from "./RefusalCard";
import { SentFiles } from "./SentFiles";
import { SoundBars } from "./SoundBars";
import { Stamp } from "./Stamp";
import { StepList } from "./StepList";
import { TranscriptBlock } from "./TranscriptBlock";

export function TurnView({ turn, onRetry, selected = false, onSelect }: {
  turn: Turn; onRetry?: () => void; selected?: boolean; onSelect?: () => void;
}) {
  const { final, refusal } = turn;
  const safety = refusal?.reason === "safety";
  const streaming = !final;
  const steps = stepsOf(turn);
  const current = streaming ? steps[steps.length - 1] : undefined;
  return (
    <article className="turn" aria-busy={streaming}>
      <div className="you">
        <span className="who">You</span>
        {turn.userText ? <p className="you__text">{turn.userText}</p> : <p className="you__text muted">(no message)</p>}
        <SentFiles files={turn.sentFiles} />
      </div>

      <section className={`bot ${selected ? "bot--selected" : ""}`} aria-label="HomeFix's answer" onClick={onSelect}>
        <header className="bot__head">
          <Stamp outcome={outcomeOf(turn)} />
          {final && final.latency_ms > 0 && <LatencyBadge latencyMs={final.latency_ms} model={final.model} />}
        </header>
        <div className="bot__body">
          {current && (
            <p className="live" aria-live="polite">
              <span className="spinner" aria-hidden="true" />
              {(STEP_TEXT[current.stage]?.title ?? current.stage)}…
            </p>
          )}
          {safety && refusal ? (
            <RefusalCard refusal={refusal} />
          ) : (
            <>
              {turn.transcript && <TranscriptBlock transcript={turn.transcript} />}
              {turn.answer && <AnswerText text={turn.answer} streaming={streaming} />}
              {turn.frames && <FrameStrip timestamps={turn.frames.timestamps} />}
              {turn.soundLabels && <SoundBars labels={turn.soundLabels.labels} />}
              {turn.citation && <CitationCard citation={turn.citation} />}
              {turn.codeResult && <CodeResultPanel result={turn.codeResult} />}
              {refusal && <RefusalCard refusal={refusal} />}
              {turn.error && <ErrorCard error={turn.error} onRetry={onRetry} />}
            </>
          )}
          {steps.length > 0 && (
            <details className="turn__steps">
              <summary>What happened, step by step</summary>
              <StepList steps={steps} compact />
            </details>
          )}
        </div>
      </section>
    </article>
  );
}
