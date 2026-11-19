import type { Turn } from "../state/reduce";
import { CitationCard } from "./CitationCard";
import { CodeResultPanel } from "./CodeResultPanel";
import { ErrorCard } from "./ErrorCard";
import { FrameStrip } from "./FrameStrip";
import { LatencyBadge } from "./LatencyBadge";
import { RefusalCard } from "./RefusalCard";
import { SoundBars } from "./SoundBars";
import { StatusChips } from "./StatusChips";
import { TranscriptBlock } from "./TranscriptBlock";

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
            {turn.transcript && <TranscriptBlock transcript={turn.transcript} />}
            {turn.frames && <FrameStrip timestamps={turn.frames.timestamps} />}
            {turn.answer && (
              <p className="answer">
                {turn.answer}
                {streaming && <span className="cursor" aria-hidden="true">▍</span>}
              </p>
            )}
            {turn.soundLabels && <SoundBars labels={turn.soundLabels.labels} />}
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
