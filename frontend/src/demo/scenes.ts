import type { HomeFixEvent } from "../contract";

export type SceneId = "problem" | "photo" | "sound" | "honesty" | "danger" | "proof";

export type Beat =
  | { kind: "title"; text: string; sub?: string }
  | { kind: "photos"; items: { src: string; caption: string }[] }
  | { kind: "promises" }
  | { kind: "media"; src: string; label?: string; audio?: boolean }
  | { kind: "turn" } // the recording, one beat per cut (see cutPoints)
  | { kind: "scores" }
  | { kind: "limits" };

export interface Scene {
  id: SceneId;
  title: string;
  note?: string;
  beats: Beat[];
}

export interface Recording {
  scene: SceneId;
  recorded_at: string;
  profile: string;
  request: { message: string; files: string[]; manual_id: string | null };
  events: HomeFixEvent[];
}

export const SCENES: Scene[] = [
  {
    id: "problem",
    title: "The problem",
    beats: [
      { kind: "title", text: "Your first apartment. Something beeps. The landlord doesn't answer." },
      {
        kind: "photos",
        items: [
          { src: "/samples/real_breaker_panel.jpg", caption: "Breaker panel" },
          { src: "/samples/real_leaking_pipe.jpg", caption: "Leaking pipe" },
          { src: "/samples/real_thermostat_66.jpg", caption: "Thermostat" },
          { src: "/samples/real_smoke_detector.jpg", caption: "Smoke detector" },
        ],
      },
      { kind: "promises" },
    ],
  },
  {
    id: "photo",
    title: "Photo to manual",
    note: "Drawn by us: no openly licensed photo of an error display exists",
    beats: [{ kind: "turn" }],
  },
  { id: "sound", title: "Sound", beats: [{ kind: "turn" }] },
  { id: "honesty", title: "Honesty", note: "Manual loaded: Unit 4B apartment guide", beats: [{ kind: "turn" }] },
  { id: "danger", title: "Danger", beats: [{ kind: "turn" }] },
  {
    id: "proof",
    title: "Proof",
    beats: [{ kind: "title", text: "Wi-Fi off. Everything ran on this laptop." }, { kind: "scores" }, { kind: "limits" }],
  },
];

const SCENE_IDS: SceneId[] = ["problem", "photo", "sound", "honesty", "danger", "proof"];
const files = import.meta.glob("./recordings/*.json", { eager: true, import: "default" }) as Record<string, Recording>;

export const RECORDINGS: Partial<Record<SceneId, Recording>> = {};
for (const [path, rec] of Object.entries(files)) {
  const id = (path.split("/").pop() ?? "").replace(/\.json$/, "") as SceneId;
  if (SCENE_IDS.includes(id)) RECORDINGS[id] = rec;
}
