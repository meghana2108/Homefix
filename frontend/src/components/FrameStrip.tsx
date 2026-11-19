import { useState } from "react";

/** Same rounding as the backend's frame labels: half-way rounds up (1.95 -> 2.0). */
export const fmt = (t: number) => (Math.round(t * 10 + 1e-9) / 10).toFixed(1);

/** A timeline with one tick per sampled frame; hover or focus a tick to see its time. */
export function FrameStrip({ timestamps }: { timestamps: number[] }) {
  const [active, setActive] = useState<number | null>(null);
  if (timestamps.length === 0) return null;
  const min = Math.min(...timestamps);
  const max = Math.max(...timestamps);
  const span = max - min;
  const left = (t: number) => (span > 0 ? Number((((t - min) / span) * 100).toFixed(2)) : 50);
  const n = timestamps.length;
  const caption = n === 1 ? `1 frame · ${fmt(min)} s` : `${n} frames · ${fmt(min)}–${fmt(max)} s`;
  return (
    <figure className="framestrip">
      <div className="framestrip__track">
        {timestamps.map((t, i) => (
          <button
            key={`${t}-${i}`}
            type="button"
            className={`framestrip__tick ${active === i ? "framestrip__tick--active" : ""}`}
            style={{ left: `${left(t)}%` }}
            aria-label={`Frame ${i + 1} at t=${fmt(t)}s`}
            onMouseEnter={() => setActive(i)}
            onMouseLeave={() => setActive((a) => (a === i ? null : a))}
            onFocus={() => setActive(i)}
            onBlur={() => setActive((a) => (a === i ? null : a))}
          >
            {active === i && <span className="framestrip__tip">t={fmt(t)}s</span>}
          </button>
        ))}
      </div>
      <figcaption className="muted">{caption}</figcaption>
    </figure>
  );
}
