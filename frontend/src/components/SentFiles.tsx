import type { SentFile } from "../state/reduce";

const ICON = { image: "🖼", audio: "🔊", video: "🎬", file: "📄" } as const;

/** What the user attached: photo thumbnails, a playable sound or clip, documents as chips. */
export function SentFiles({ files }: { files: SentFile[] }) {
  if (files.length === 0) return null;
  return (
    <ul className="sent">
      {files.map((f, i) => (
        <li key={`${f.name}-${i}`} className={`sent__item sent__item--${f.kind}`}>
          {f.url && f.kind === "image" && <img className="sent__img" src={f.url} alt={f.name} />}
          {f.url && f.kind === "audio" && <audio className="sent__audio" src={f.url} controls preload="metadata" aria-label={f.name} />}
          {f.url && f.kind === "video" && <video className="sent__video" src={f.url} controls muted preload="metadata" aria-label={f.name} />}
          <span className="file"><span aria-hidden="true">{ICON[f.kind]} </span>{f.name}</span>
        </li>
      ))}
    </ul>
  );
}
