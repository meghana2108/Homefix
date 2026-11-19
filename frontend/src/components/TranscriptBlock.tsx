import type { TranscriptEvent } from "../contract";

/** Whisper's transcript, shown as a quote above the answer. */
export function TranscriptBlock({ transcript }: { transcript: TranscriptEvent }) {
  return (
    <figure className="transcript">
      <figcaption className="muted">Transcript · {transcript.seconds.toFixed(1)} s</figcaption>
      <blockquote>{transcript.text.trim() ? transcript.text : <span className="muted">(no words heard)</span>}</blockquote>
    </figure>
  );
}
