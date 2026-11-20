import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { expandBeats, firstBeatOf, turnAt, type Flat } from "../../demo/beats";
import { RECORDINGS, SCENES, type Beat, type Recording, type Scene, type SceneId } from "../../demo/scenes";
import { SCORES, SCORE_RUNS } from "../../demo/scores";
import { TurnView } from "../TurnView";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-11-20T11:28:17" -> "20 Nov 2026". A fixed month list, so it never depends on the locale. */
export function recordedDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1] ?? m[2]} ${m[1]}`;
}

const MISSING_MEDIA = "Run scripts/fetch_real_samples.py";

function Photo({ src, caption }: { src: string; caption: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <figure className="demo__photo">
      {failed
        ? <div className="demo__missing" role="note">{caption}: this photo is missing. {MISSING_MEDIA}</div>
        : <img src={src} alt={caption} onError={() => setFailed(true)} />}
      <figcaption>{caption}</figcaption>
    </figure>
  );
}

const PROMISES = [
  "It runs on this laptop. No Wi-Fi, no cloud.",
  "Every manual answer shows the page and the exact words, or says the manual doesn't say.",
  "If it sounds dangerous, it says stop first and gives no repair steps.",
];

function limitsOf() {
  const video = SCORES.find((s) => s.row.startsWith("Video"));
  const refusals = SCORES.find((s) => s.row === "Text refusals");
  return [
    video && `Video is our weakest part: ${video.full} on the full profile, ${video.lite} on lite.`,
    refusals && `Text refusals: ${refusals.full} on full, ${refusals.lite} on lite. It still answers sometimes when it should say it doesn't know.`,
    "The error-display photo in scene 2 is drawn by us, because no openly licensed photo of one exists.",
  ].filter((x): x is string => !!x);
}

function BeatView({ beat }: { beat: Beat }) {
  switch (beat.kind) {
    case "title":
      return (
        <div className="demo__beat">
          <h2 className="demo__title">{beat.text}</h2>
          {beat.sub && <p className="demo__sub">{beat.sub}</p>}
        </div>
      );
    case "photos":
      return (
        <div className="demo__beat demo__photos">
          {beat.items.map((p) => <Photo key={p.src} src={p.src} caption={p.caption} />)}
        </div>
      );
    case "promises":
      return (
        <ul className="demo__beat demo__list">{PROMISES.map((p) => <li key={p}>{p}</li>)}</ul>
      );
    case "media":
      return (
        <div className="demo__beat">
          {beat.audio ? <audio src={beat.src} controls aria-label={beat.label ?? "Sound"} /> : <Photo src={beat.src} caption={beat.label ?? ""} />}
        </div>
      );
    case "scores":
      return (
        <div className="demo__beat">
          <table className="demo__scores">
            <caption>Practice-set scores, from {SCORE_RUNS.full} and {SCORE_RUNS.lite}</caption>
            <thead><tr><th scope="col">Test</th><th scope="col">Full (M4)</th><th scope="col">Lite (M2)</th></tr></thead>
            <tbody>
              {SCORES.map((s) => <tr key={s.row}><th scope="row">{s.row}</th><td>{s.full}</td><td>{s.lite}</td></tr>)}
            </tbody>
          </table>
        </div>
      );
    case "limits":
      return (
        <div className="demo__beat">
          <ul className="demo__list">{limitsOf().map((l) => <li key={l}>{l}</li>)}</ul>
          <p className="demo__credit">Photos and sounds: Wikimedia Commons, see ASSETS.md</p>
        </div>
      );
    default:
      return null;
  }
}

const typing = (t: EventTarget | null) =>
  t instanceof HTMLElement && (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || t.isContentEditable);

export function DemoPage({ scenes = SCENES, recordings = RECORDINGS }: {
  scenes?: Scene[]; recordings?: Partial<Record<SceneId, Recording>>;
} = {}) {
  const flat: Flat[] = useMemo(() => expandBeats(scenes, recordings), [scenes, recordings]);
  const [idx, setIdx] = useState(0);
  const [blocked, setBlocked] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const last = flat.length - 1;

  const jump = useCallback((scene: number) => {
    const i = firstBeatOf(flat, scene);
    if (i >= 0) setIdx(i);
  }, [flat]);

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key;
      if (k === "ArrowRight" || k === " " || k === "PageDown") { e.preventDefault(); setIdx((i) => Math.min(last, i + 1)); }
      else if (k === "ArrowLeft" || k === "PageUp") { e.preventDefault(); setIdx((i) => Math.max(0, i - 1)); }
      else if (k === "Escape") window.location.hash = "#/ask";
      else if (k === "f" || k === "F") {
        if (document.fullscreenElement) void document.exitFullscreen?.();
        else void document.documentElement.requestFullscreen?.()?.catch?.(() => undefined);
      } else if (/^[1-9]$/.test(k)) jump(Number(k) - 1);
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [last, jump]);

  const cur = flat[Math.min(idx, last)];
  const scene = scenes[cur?.scene ?? 0];
  const rec = scene ? recordings[scene.id] : undefined;
  const upto = flat.map((f, i) => ({ f, i })).filter(({ f, i }) => f.scene === cur?.scene && i <= idx);
  const lastTurn = [...upto].reverse().find(({ f }) => f.kind === "turn");
  const firstTurn = flat.findIndex((f) => f.scene === cur?.scene && f.kind === "turn");
  const clip = scene?.id === "sound" && rec ? rec.request.files[0] : undefined;
  const playing = !!clip && lastTurn?.i !== undefined && firstTurn >= 0 && idx >= firstTurn;

  useEffect(() => {
    setBlocked(false);
    if (!playing) return;
    const p = audioRef.current?.play?.();
    p?.catch(() => setBlocked(true));
  }, [playing, clip]);

  const replay = () => {
    const p = audioRef.current?.play?.();
    setBlocked(false);
    p?.catch(() => setBlocked(true));
  };

  if (!cur || !scene) return <main className="demo"><p className="demo__missing">Nothing to show.</p></main>;

  return (
    <main className="demo">
      <nav className="demo__strip" aria-label="Scenes">
        {scenes.map((s, i) => (
          <button key={s.id} type="button" className="demo__tab" aria-current={i === cur.scene ? "step" : undefined} onClick={() => jump(i)}>
            <span aria-hidden="true">{i + 1} </span>{s.title}
          </button>
        ))}
      </nav>

      <div className="demo__stage" key={cur.scene}>
        {upto.map(({ f, i }) => {
          if (f.kind === "missing") {
            return <p key={i} className="demo__missing" role="note">This scene hasn't been recorded. Run scripts/record_demo.py.</p>;
          }
          if (f.kind === "turn") {
            if (i !== lastTurn?.i || !rec) return null;
            return (
              <div key="turn" className="demo__beat demo__turn">
                <TurnView turn={turnAt(rec, f.upTo ?? 0)} />
              </div>
            );
          }
          return <BeatView key={i} beat={f.beat!} />;
        })}
        {clip && playing && <audio ref={audioRef} src={clip} preload="auto" hidden />}
        {blocked && <button type="button" className="btn demo__play" onClick={replay}>Play the sound</button>}
      </div>

      {scene.note && <p className="demo__note">{scene.note}</p>}
      {rec && cur.kind !== "missing" && (
        <p className="demo__label">
          Recorded on the {rec.profile === "lite" ? "M2" : "M4"}, {rec.profile} profile, {recordedDate(rec.recorded_at)}
        </p>
      )}
      <p className="demo__hint" aria-hidden="true">{idx + 1} / {flat.length} &nbsp; → next &nbsp; ← back &nbsp; 1-{scenes.length} scenes &nbsp; F full screen &nbsp; Esc open the app</p>
    </main>
  );
}
