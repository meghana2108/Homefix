import type { HomeFixEvent } from "../contract";

/** Each value k means "show events.slice(0, k)". Tokens fold into the next cut. */
export function cutPoints(events: HomeFixEvent[]): number[] {
  const cuts: number[] = [];
  let prevStage: string | null = null;
  events.forEach((e, i) => {
    let cut = false;
    if (e.type === "status") {
      cut = e.stage !== prevStage;
      prevStage = e.stage;
    } else {
      cut = ["transcript", "sound_labels", "citation", "refusal", "final"].includes(e.type);
    }
    if (cut) cuts.push(i + 1);
  });
  return cuts;
}
