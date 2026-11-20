/** A small seven-segment display, as on a washer panel. Segments: a top, b top-right, c bottom-right,
 *  d bottom, e bottom-left, f top-left, g middle. */
const DIGITS: Record<string, string> = {
  "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc",
  "7": "abc", "8": "abcdefg", "9": "abcfgd", E: "afged", F: "afge", C: "afed", H: "fbgec", L: "fed", P: "abfge", U: "fbcde", "-": "g",
};

function Digit({ ch, x }: { ch: string; x: number }) {
  const on = DIGITS[ch] ?? "";
  const w = 34, h = 62, t = 7;
  const seg: Record<string, [number, number, number, number]> = {
    a: [t, 0, w - 2 * t, t], d: [t, h - t, w - 2 * t, t], g: [t, h / 2 - t / 2, w - 2 * t, t],
    f: [0, t, t, h / 2 - t * 1.5], b: [w - t, t, t, h / 2 - t * 1.5],
    e: [0, h / 2 + t / 2, t, h / 2 - t * 1.5], c: [w - t, h / 2 + t / 2, t, h / 2 - t * 1.5],
  };
  return (
    <g transform={`translate(${x} 0) skewX(-6)`}>
      {Object.entries(seg).map(([k, [sx, sy, sw, sh]]) => (
        <rect key={k} x={sx} y={sy} width={sw} height={sh} rx={2.5} fill={on.includes(k) ? "var(--seg)" : "var(--seg-dim)"} />
      ))}
    </g>
  );
}

export function SevenSeg({ text, label }: { text: string; label: string }) {
  const chars = text.split("");
  const width = chars.length * 46 + 120;
  return (
    <svg viewBox={`0 0 ${width} 96`} role="img" aria-label={label}>
      <rect x="0" y="0" width={width - 88} height="96" rx="8" fill="var(--panel)" />
      <g transform="translate(18 17)">
        {chars.map((c, i) => <Digit key={i} ch={c} x={i * 46} />)}
      </g>
      <text x={width - 74} y="34" fill="var(--panel-ink)" fontSize="13" fontFamily="IBM Plex Sans, sans-serif">°C</text>
      <text x={width - 74} y="62" fill="var(--panel-ink)" fontSize="13" fontFamily="IBM Plex Sans, sans-serif">rpm</text>
    </svg>
  );
}
