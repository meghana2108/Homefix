import { useEffect, useRef, useState, type KeyboardEvent, type MutableRefObject } from "react";
import { Camera, CornerDownRight, FileText, Film, Paperclip, Send, Volume2, X } from "lucide-react";
import type { Manual } from "../contract";
import { kindOf } from "../state/reduce";
import { ManualPicker } from "./ManualPicker";
import { Icon } from "./Icons";
import { MicButton, type MicHandle } from "./MicButton";

export const MAX_FILES = 4;
export const ACCEPT = [
  "image/*", "audio/*", "video/*", ".heic", ".heif", ".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".py",
].join(",");
const ICON = { image: Camera, audio: Volume2, video: Film, file: FileText } as const;

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
  onManual, inputRef, replying = null }: {
  text: string;
  onText: (t: string) => void;
  files: File[];
  onFiles: (f: File[]) => void;
  /** With `what`, send exactly that (the mic just finished); without, the parent sends its own text and files. */
  onSend: (what?: { text: string; files: File[] }) => void;
  busy: boolean;
  note: string | null;
  manuals?: Manual[];
  manualId?: string | null;
  onManual?: (id: string | null) => void;
  inputRef?: MutableRefObject<HTMLInputElement | null>;
  /** HomeFix asked a question back; what's typed answers it, with the files sent before. */
  replying?: { files: number; onCancel: () => void } | null;
}) {
  const ownInput = useRef<HTMLInputElement | null>(null);
  const input = inputRef ?? ownInput;
  const [partial, setPartial] = useState("");
  const [micNote, setMicNote] = useState<string | null>(null);
  useEffect(() => { if (busy) setMicNote(null); }, [busy]);
  const mic = useRef<MicHandle | null>(null);
  // Ask pressed while the mic was on: stop it, and send once its words or recording are in.
  const [waitingForMic, setWaitingForMic] = useState(false);
  const sendAfterMic = useRef(false);
  const finishSend = (what: { text: string; files: File[] }) => {
    sendAfterMic.current = false;
    setWaitingForMic(false);
    onSend(what);
  };
  const submit = () => {
    if (busy || sendAfterMic.current) return;
    if (mic.current?.busy()) {
      sendAfterMic.current = true;
      setWaitingForMic(true);
      mic.current.stop();
      return;
    }
    onSend();
  };
  const onMicSound = (f: File) => {
    const nextFiles = [...files, f];
    const nextText = text.trim() ? text : "What is this sound?";
    onFiles(nextFiles);
    if (nextText !== text) onText(nextText);
    if (sendAfterMic.current) return finishSend({ text: nextText.trim(), files: nextFiles });
    setMicNote("That wasn't speech, so the recording is attached as a sound. Press Ask to find out what it is.");
  };
  const previews = usePreviews(files);
  const onMicFinal = (spoken: string) => {
    const said = spoken.trim();
    const next = said ? (text.trim() ? `${text.trim()} ${said}` : said) : text;
    if (said) onText(next);
    if (sendAfterMic.current) finishSend({ text: next.trim(), files });
  };
  const onMicFail = () => { if (sendAfterMic.current) finishSend({ text: text.trim(), files }); };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };
  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <div className="composer__box">
        {partial && (
          <div className="mic-partial" aria-live="polite"><span className="sr-only">Hearing: </span><span>{partial}</span></div>
        )}
        {replying && (
          <div className="replying">
            <Icon as={CornerDownRight} size={16} />
            <span>Answering HomeFix's question{replying.files > 0 ? `, with your ${replying.files === 1 ? "file" : "files"}` : ""}</span>
            <button type="button" className="linkbtn replying__x" onClick={replying.onCancel}>Ask something new instead</button>
          </div>
        )}
        {micNote && <p className="mic-note" role="status">{micNote}</p>}
        {(files.length > 0 || note) && (
          <div className="composer__files">
            {files.map((f, i) => (
              <span key={`${f.name}-${i}`} className="file file--pending">
                {previews[i]
                  ? <img className="file__thumb" src={previews[i]!} alt="" />
                  : <Icon as={ICON[kindOf(f.name, f.type)]} size={16} />}
                {f.name}
                <button type="button" className="file__remove" aria-label={`Remove ${f.name}`}
                  onClick={() => onFiles(files.filter((_, j) => j !== i))}><Icon as={X} size={16} /></button>
              </span>
            ))}
            {note && <span className="muted">{note}</span>}
          </div>
        )}
        <textarea className="composer__text" rows={2}
          placeholder={replying ? "Type your answer, like “It's the clock on my cooktop”…"
            : "Ask about something at home, or drop a photo, sound, video or file…"}
          value={text} aria-label="Question" onChange={(e) => onText(e.target.value)} onKeyDown={onKey} />
        <div className="composer__row">
          <button type="button" className="btn btn--icon" aria-label="Attach files" title="Attach a photo, sound, video or file"
            onClick={() => { if (input.current) { input.current.accept = ACCEPT; input.current.click(); } }}>
            <Icon as={Paperclip} /><span className="btn__text">Attach</span>
          </button>
          <input ref={input} type="file" multiple accept={ACCEPT} hidden
            onChange={(e) => {
              onFiles([...files, ...Array.from(e.target.files ?? [])]);
              e.target.value = "";
              e.target.accept = ACCEPT;
            }} />
          <MicButton ref={mic} onPartial={setPartial} onFinal={(t) => { setMicNote(null); onMicFinal(t); }}
            onSound={onMicSound} onFail={onMicFail} disabled={busy} />
          {onManual && <ManualPicker manuals={manuals} value={manualId} onChange={onManual} />}
          <span className="composer__spacer" />
          <button type="submit" className="btn btn--primary" disabled={busy || waitingForMic}>
            <Icon as={Send} size={16} />{busy ? "Working…" : waitingForMic ? "Stopping the mic…" : "Ask"}
          </button>
        </div>
      </div>
      <p className="composer__hint">Press Enter to ask, Shift and Enter for a new line. Nothing you send leaves this laptop.</p>
    </form>
  );
}
