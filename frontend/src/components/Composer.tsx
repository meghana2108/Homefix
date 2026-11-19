import { useEffect, useRef, useState, type KeyboardEvent, type MutableRefObject } from "react";
import type { Manual } from "../contract";
import { kindOf } from "../state/reduce";
import { ManualPicker } from "./ManualPicker";
import { MicButton } from "./MicButton";

export const MAX_FILES = 4;
export const ACCEPT = [
  "image/*", "audio/*", "video/*", ".heic", ".heif", ".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".py",
].join(",");
const ICON = { image: "🖼", audio: "🔊", video: "🎬", file: "📄" } as const;

/** Object URLs for image previews, revoked when the files change. Empty where the browser has none (tests). */
function usePreviews(files: File[]): (string | null)[] {
  const [urls, setUrls] = useState<(string | null)[]>([]);
  useEffect(() => {
    const canPreview = typeof URL !== "undefined" && typeof URL.createObjectURL === "function";
    const next = files.map((f) => (canPreview && kindOf(f.name, f.type) === "image" ? URL.createObjectURL(f) : null));
    setUrls(next);
    return () => next.forEach((u) => u && URL.revokeObjectURL(u));
  }, [files]);
  return urls;
}

export function Composer({ text, onText, files, onFiles, onSend, busy, note, manuals = [], manualId = null,
  onManual, inputRef }: {
  text: string;
  onText: (t: string) => void;
  files: File[];
  onFiles: (f: File[]) => void;
  onSend: () => void;
  busy: boolean;
  note: string | null;
  manuals?: Manual[];
  manualId?: string | null;
  onManual?: (id: string | null) => void;
  inputRef?: MutableRefObject<HTMLInputElement | null>;
}) {
  const ownInput = useRef<HTMLInputElement | null>(null);
  const input = inputRef ?? ownInput;
  const [partial, setPartial] = useState("");
  const previews = usePreviews(files);
  const onMicFinal = (spoken: string) => {
    const said = spoken.trim();
    if (said) onText(text.trim() ? `${text.trim()} ${said}` : said);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (!busy) onSend();
    }
  };
  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); if (!busy) onSend(); }}>
      <div className="composer__box">
        {partial && (
          <div className="mic-partial" aria-live="polite">🎤 <span>{partial}</span></div>
        )}
        {(files.length > 0 || note) && (
          <div className="composer__files">
            {files.map((f, i) => (
              <span key={`${f.name}-${i}`} className="file file--pending">
                {previews[i]
                  ? <img className="file__thumb" src={previews[i]!} alt="" />
                  : <span aria-hidden="true">{ICON[kindOf(f.name, f.type)]} </span>}
                {f.name}
                <button type="button" className="file__remove" aria-label={`Remove ${f.name}`}
                  onClick={() => onFiles(files.filter((_, j) => j !== i))}>×</button>
              </span>
            ))}
            {note && <span className="muted">{note}</span>}
          </div>
        )}
        <textarea className="composer__text" rows={2} placeholder="Ask about something at home, or drop a photo, sound, video or file…"
          value={text} aria-label="Question" onChange={(e) => onText(e.target.value)} onKeyDown={onKey} />
        <div className="composer__row">
          <button type="button" className="btn btn--ghost" aria-label="Attach files" title="Attach a photo, sound, video or file"
            onClick={() => { if (input.current) { input.current.accept = ACCEPT; input.current.click(); } }}>
            📎 <span className="btn__text">Attach</span>
          </button>
          <input ref={input} type="file" multiple accept={ACCEPT} hidden
            onChange={(e) => {
              onFiles([...files, ...Array.from(e.target.files ?? [])]);
              e.target.value = "";
              e.target.accept = ACCEPT;
            }} />
          <MicButton onPartial={setPartial} onFinal={onMicFinal} disabled={busy} />
          {onManual && <ManualPicker manuals={manuals} value={manualId} onChange={onManual} />}
          <span className="composer__spacer" />
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? "Working…" : "Ask"}
          </button>
        </div>
      </div>
      <p className="composer__hint muted">Enter to send · Shift+Enter for a new line · Everything stays on this laptop</p>
    </form>
  );
}
