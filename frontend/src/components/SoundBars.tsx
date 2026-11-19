import { Ear } from "lucide-react";
import type { SoundLabelsEvent } from "../contract";
import { Icon } from "./Icons";

const clampPct = (score: number) => Math.min(100, Math.max(0, Math.round(score * 100)));

/** Top sound labels as horizontal bars: name, whole percent, bar width = score. */
export function SoundBars({ labels }: { labels: SoundLabelsEvent["labels"] }) {
  if (labels.length === 0) return null;
  return (
    <section className="evidence">
      <p className="evidence__label"><Icon as={Ear} size={16} />The closest matching sounds</p>
      <ul className="soundbars" aria-label="Sounds heard">
        {labels.map((l) => {
          const pct = clampPct(l.score);
          return (
            <li key={l.label} className="soundbar">
              <span className="soundbar__label">{l.label}</span><span className="soundbar__pct">{pct}%</span>
              <span className="soundbar__track" aria-hidden="true">
                <span className="soundbar__fill" style={{ width: `${Math.max(1, pct)}%` }} />
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
