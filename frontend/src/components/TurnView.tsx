import type { Turn } from "../state/reduce";
import { CitationCard } from "./CitationCard";
import { CodeResultPanel } from "./CodeResultPanel";
import { ErrorCard } from "./ErrorCard";
import { LatencyBadge } from "./LatencyBadge";
import { RefusalCard } from "./RefusalCard";
import { StatusChips } from "./StatusChips";

export function TurnView({ turn, onRetry }: { turn: Turn; onRetry?: () => void }) {
  const { final, refusal } = turn;
  const safety = refusal?.reason === "safety";
  const streaming = !final;
  return (
    <article className="turn" aria-busy={streaming}>
      <div className="you">
        <span className="who">You</span>
        {turn.userText ? <p>{turn.userText}</p> : <p className="muted">(no message)</p>}
        {turn.fileNames.length > 0 && (
          <ul className="files">
            {turn.fileNames.map((n, i) => <li key={`${n}-${i}`} className="file">📎 {n}</li>)}
          </ul>
        )}
      </div>

      <div className="bot">
        <span className="who">HomeFix</span>
        <StatusChips statuses={turn.statuses} />

        {safety && refusal ? (
          <RefusalCard refusal={refusal} />
        ) : (
          <>
            {turn.transcript && (
              <blockquote className="transcript">
                “{turn.transcript.text}” <span className="muted">({turn.transcript.seconds.toFixed(1)} s)</span>
              </blockquote>
            )}
            {turn.answer && (
              <p className="answer">
                {turn.answer}
                {streaming && <span className="cursor" aria-hidden="true">▍</span>}
              </p>
            )}
            {turn.soundLabels && (
              <ul className="sounds">
                {turn.soundLabels.labels.map((l) => (
                  <li key={l.label}>{l.label} {Math.round(l.score * 100)}%</li>
                ))}
              </ul>
            )}
            {turn.frames && turn.frames.timestamps.length > 0 && (
              <p className="muted">
                {turn.frames.timestamps.length} frames, t={turn.frames.timestamps[0].toFixed(1)}s to
                t={turn.frames.timestamps[turn.frames.timestamps.length - 1].toFixed(1)}s
              </p>
            )}
            {turn.citation && <CitationCard citation={turn.citation} />}
            {turn.codeResult && <CodeResultPanel result={turn.codeResult} />}
            {refusal && <RefusalCard refusal={refusal} />}
            {turn.error && <ErrorCard error={turn.error} onRetry={onRetry} />}
          </>
        )}

        {final && final.latency_ms > 0 && <LatencyBadge latencyMs={final.latency_ms} model={final.model} />}
      </div>
    </article>
  );
}
