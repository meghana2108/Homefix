import { useRef, useState, type KeyboardEvent } from "react";
import { MicButton } from "./MicButton";

export const MAX_FILES = 4;
const ACCEPT = [
  "image/*", "audio/*", "video/*", ".heic", ".heif", ".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".py",
].join(",");

export function Composer({ text, onText, files, onFiles, onSend, busy, note }: {
  text: string;
  onText: (t: string) => void;
  files: File[];
  onFiles: (f: File[]) => void;
  onSend: () => void;
  busy: boolean;
  note: string | null;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [partial, setPartial] = useState("");
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
      {partial && (
        <div className="mic-partial" aria-live="polite">🎤 <span>{partial}</span></div>
      )}
      {(files.length > 0 || note) && (
        <div className="composer__files">
          {files.map((f, i) => (
            <span key={`${f.name}-${i}`} className="file">
              📎 {f.name}
              <button type="button" className="file__remove" aria-label={`Remove ${f.name}`}
                onClick={() => onFiles(files.filter((_, j) => j !== i))}>×</button>
            </span>
          ))}
          {note && <span className="muted">{note}</span>}
        </div>
      )}
      <div className="composer__row">
        <button type="button" className="btn btn--icon" aria-label="Attach files" title="Attach files"
          onClick={() => input.current?.click()}>📎</button>
        <input ref={input} type="file" multiple accept={ACCEPT} hidden
          onChange={(e) => {
            onFiles([...files, ...Array.from(e.target.files ?? [])]);
            e.target.value = "";
          }} />
        <textarea className="composer__text" rows={1} placeholder="Type a question…" value={text}
          aria-label="Question" onChange={(e) => onText(e.target.value)} onKeyDown={onKey} />
        <MicButton onPartial={setPartial} onFinal={onMicFinal} disabled={busy} />
        <button type="submit" className="btn btn--primary" disabled={busy}>Send</button>
      </div>
    </form>
  );
}
