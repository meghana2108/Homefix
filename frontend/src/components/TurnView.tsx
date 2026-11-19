import type { Turn } from "../state/reduce";
import { AnswerText } from "./AnswerText";
import { CitationCard } from "./CitationCard";
import { CodeResultPanel } from "./CodeResultPanel";
import { ErrorCard } from "./ErrorCard";
import { FrameStrip } from "./FrameStrip";
import { LatencyBadge } from "./LatencyBadge";
import { Logo } from "./Logo";
import { Progress } from "./Progress";
import { RefusalCard } from "./RefusalCard";
import { SentFiles } from "./SentFiles";
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
        <SentFiles files={turn.sentFiles} />
      </div>

      <div className="bot">
        <div className="bot__head">
          <Logo size={22} />
          <span className="who">HomeFix</span>
        </div>
        <Progress statuses={turn.statuses} done={!streaming} />

        {safety && refusal ? (
          <RefusalCard refusal={refusal} />
        ) : (
          <>
            {turn.transcript && <TranscriptBlock transcript={turn.transcript} />}
            {turn.frames && <FrameStrip timestamps={turn.frames.timestamps} />}
            {turn.answer && <AnswerText text={turn.answer} streaming={streaming} />}
            {turn.soundLabels && <SoundBars labels={turn.soundLabels.labels} />}
            {turn.citation && <CitationCard citation={turn.citation} />}
            {turn.codeResult && <CodeResultPanel result={turn.codeResult} />}
            {refusal && <RefusalCard refusal={refusal} />}
            {turn.error && <ErrorCard error={turn.error} onRetry={onRetry} />}
          </>
        )}

        {(final || turn.statuses.length > 0) && (
          <div className="bot__foot">
            {final && final.latency_ms > 0 && <LatencyBadge latencyMs={final.latency_ms} model={final.model} />}
            {turn.statuses.length > 0 && (
              <details className="how">
                <summary>How I got this</summary>
                <StatusChips statuses={turn.statuses} />
                {final?.model && <p className="muted how__model">Model: {final.model} · ran on this laptop</p>}
              </details>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
