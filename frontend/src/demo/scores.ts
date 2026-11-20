export const SCORE_RUNS = { full: "20261120-1009-full-all" };

/** The organizers' practice pack: 25 image, 20 audio, 20 text, 20 code, 15 video. */
export const PACK_ITEMS = 100;

/** From results/summary_full.md. The second number of each score is how many questions were tested. */
export const SCORES: { row: string; full: string }[] = [
  { row: "Image count", full: "14/15" },
  { row: "Image, other questions", full: "8/10" },
  { row: "Sound top-1", full: "8/10" },
  { row: "Speech answers", full: "8/10" },
  { row: "Text answers", full: "15/15" },
  { row: "Text refusals", full: "3/5" },
  { row: "Code pass@1", full: "20/20" },
  { row: "Video (all metrics)", full: "11/15" },
];

/** `uv run pytest` and `cd frontend && npx vitest run` on main. Update when the counts change. */
export const OUR_TESTS = { backend: 807, frontend: 170, on: "20 Nov 2026" };
