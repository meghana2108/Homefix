import { kindOf, newTurn, reduce, type SentFile, type Turn } from "../state/reduce";
import { cutPoints } from "./cuts";
import type { Beat, Recording, Scene, SceneId } from "./scenes";

export type Flat = { scene: number; kind: Beat["kind"] | "missing"; upTo?: number; beat: Beat | null };

function usable(rec: Recording | undefined): rec is Recording {
  return !!rec && rec.events.some((e) => e.type === "final");
}

export function expandBeats(scenes: Scene[], recs: Partial<Record<SceneId, Recording>>): Flat[] {
  const out: Flat[] = [];
  scenes.forEach((s, scene) => {
    if (s.beats.some((b) => b.kind === "turn") && !usable(recs[s.id])) {
      out.push({ scene, kind: "missing", beat: null });
      return;
    }
    for (const beat of s.beats) {
      if (beat.kind === "turn") {
        for (const upTo of cutPoints(recs[s.id]!.events)) out.push({ scene, kind: "turn", upTo, beat });
      } else {
        out.push({ scene, kind: beat.kind, beat });
      }
    }
  });
  return out;
}

export function turnAt(rec: Recording, upTo: number): Turn {
  const sent: SentFile[] = rec.request.files.map((url) => {
    const name = url.split("/").pop() ?? url;
    return { name, kind: kindOf(name), url };
  });
  let turn = newTurn(rec.request.message, sent.map((f) => f.name), sent);
  for (const e of rec.events.slice(0, upTo)) turn = reduce(turn, e);
  return turn;
}

export function firstBeatOf(flat: Flat[], scene: number): number {
  return flat.findIndex((f) => f.scene === scene);
}
