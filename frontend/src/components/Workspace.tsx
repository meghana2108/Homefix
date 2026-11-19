import { Camera, ChevronRight, FileText, Lock, OctagonAlert, Plus, ShieldCheck, Volume2, Zap, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { API_LABEL, IS_MOCK, getHealth, getManuals, streamChat } from "../api/client";
import type { Health, HomeFixEvent, Manual } from "../contract";
import { kindOf, newTurn, reduce, type SentFile, type Turn } from "../state/reduce";
import { stepsOf } from "../state/steps";
import { BackendBanner } from "./BackendBanner";
import { ACCEPT, Composer, MAX_FILES } from "./Composer";
import { Icon } from "./Icons";
import { AUTO } from "./ManualPicker";
import { MessageList } from "./MessageList";
import { StepList } from "./StepList";
import { Wordmark } from "./Wordmark";

const HEALTH_EVERY_MS = 5000;
const TOO_MANY = `Attach up to ${MAX_FILES} files at a time.`;
const MACHINE: Record<string, string> = { full: "M4", lite: "M2" };

/** The quick starts on an empty workspace: a question, and the kind of file to pick for it. */
export interface QuickStart {
  icon: LucideIcon;
  title: string;
  text: string;
  example: string;
  attach?: "image" | "audio" | "video" | "document";
}
export const QUICK_STARTS: QuickStart[] = [
  { icon: Camera, title: "A code on a display", text: "Take a photo of the panel. HomeFix reads the code and looks it up.",
    example: "My washer shows this code. What should I do?", attach: "image" },
  { icon: Volume2, title: "A beep or a strange noise", text: "Record it or drop the file. HomeFix names the closest sounds.",
    example: "What is this sound?", attach: "audio" },
  { icon: FileText, title: "A question for the manual", text: "Ask in plain words. You get the answer and the page it came from.",
    example: "How do I clean the drain filter?" },
  { icon: OctagonAlert, title: "Something smells, sparks or burns", text: "HomeFix tells you to stop and who to call.",
    example: "I smell burning from the outlet behind the fridge" },
  { icon: Zap, title: "A high power bill", text: "Drop a smart-plug CSV. HomeFix writes and tests a small program.",
    example: "Write a function that finds the hour with the highest watts in my smart-plug CSV" },
];
const PICK_ACCEPT: Record<NonNullable<QuickStart["attach"]>, string> = {
  image: "image/*,.heic,.heif", audio: "audio/*", video: "video/*", document: ".pdf,.docx,.txt,.md",
};

interface Sent { text: string; files: File[]; manualId: string | null }

function useOnline(): boolean {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}

function sentFiles(files: File[]): SentFile[] {
  const canPreview = typeof URL !== "undefined" && typeof URL.createObjectURL === "function";
  return files.map((f) => {
    const kind = kindOf(f.name, f.type);
    return { name: f.name, kind, url: canPreview && kind !== "file" ? URL.createObjectURL(f) : null };
  });
}

export function StartScreen({ onPick }: { onPick: (example: string, attach?: QuickStart["attach"]) => void }) {
  return (
    <section className="start" aria-labelledby="start-h">
      <div className="start__inner">
        <h1 id="start-h">What's going on at home?</h1>
        <p className="start__lead">
          Type a question below, or start from one of these. Attach a photo, a sound, a clip or a document, and
          HomeFix answers from it. You'll see each step as it works.
        </p>
        <ul className="quick" aria-label="Start from an example">
          {QUICK_STARTS.map((q) => (
            <li key={q.title}>
              <button type="button" onClick={() => onPick(q.example, q.attach)}>
                <Icon as={q.icon} size={20} />
                <span className="quick__title">{q.title}</span>
                <span className="quick__text">{q.text}</span>
                <Icon as={ChevronRight} size={18} className="quick__go" />
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Rail({ turn }: { turn: Turn | null }) {
  const steps = turn ? stepsOf(turn) : [];
  return (
    <aside className="rail" aria-labelledby="rail-h">
      <h2 id="rail-h">What happened to your question</h2>
      <p className="rail__sub">{turn ? `“${turn.userText || turn.fileNames[0] || "Your question"}”` : "Each step shows here as HomeFix works."}</p>
      {steps.length > 0 ? <StepList steps={steps} /> : (
        <p className="rail__empty">
          First HomeFix checks for danger. Then it picks how to answer, reads what you sent, and checks any quote
          against the document before it shows you anything.
        </p>
      )}
      <div className="rail__foot">
        <p><Icon as={Lock} size={16} />Every model runs on this laptop. Nothing you send leaves it.</p>
        <p><Icon as={ShieldCheck} size={16} />No word-for-word quote from a document, no answer from it.</p>
      </div>
    </aside>
  );
}

/** The app: the rail of steps for the selected question, the conversation, and the composer. */
export function Workspace() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [files, setFilesRaw] = useState<File[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  const [manuals, setManuals] = useState<Manual[]>([]);
  const [manualId, setManualId] = useState<string | null>(AUTO);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const online = useOnline();
  const sent = useRef(new Map<string, Sent>());

  // Health every 5 s drives the "can't reach" banner; manuals reload whenever the backend comes back.
  useEffect(() => {
    let alive = true;
    let wasUp = false;
    const check = async () => {
      try {
        const h = await getHealth();
        if (!alive) return;
        setHealth(h);
        setDown(false);
        if (!wasUp) {
          wasUp = true;
          getManuals().then((m) => alive && setManuals(Array.isArray(m) ? m : [])).catch(() => {});
        }
      } catch {
        if (!alive) return;
        wasUp = false;
        setDown(true);
      }
    };
    check();
    const id = window.setInterval(check, HEALTH_EVERY_MS);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (manualId && manualId !== AUTO && !manuals.some((m) => m.id === manualId)) setManualId(AUTO);
  }, [manuals, manualId]);

  const setFiles = (next: File[]) => {
    setNote(next.length > MAX_FILES ? TOO_MANY : null);
    setFilesRaw(next.slice(0, MAX_FILES));
  };

  const busy = turns.length > 0 && turns[turns.length - 1].final === null;

  const run = useCallback(async (req: Sent) => {
    const turn = newTurn(req.text, req.files.map((f) => f.name), sentFiles(req.files));
    sent.current.set(turn.id, req);
    setTurns((ts) => [...ts, turn]);
    setSelectedId(turn.id);
    const apply = (ev: HomeFixEvent) =>
      setTurns((ts) => ts.map((t) => (t.id === turn.id ? reduce(t, ev) : t)));

    const form = new FormData();
    form.append("message", req.text);
    req.files.forEach((f) => form.append("files", f, f.name));
    if (req.manualId) form.append("manual_id", req.manualId);

    let gotFinal = false;
    try {
      await streamChat(form, (ev) => {
        if (ev.type === "final") gotFinal = true;
        apply(ev);
      });
    } catch {
      // network failure; handled below
    }
    if (!gotFinal) {
      // The stream broke or the server is down: end the turn so Ask works again.
      apply({ type: "error", stage: "converting", retryable: true,
        message: `Can't reach HomeFix at ${API_LABEL}. Is the server running?` });
      apply({ type: "final", answer: "", modality: "none", question_type: "none", latency_ms: 0,
        profile: health?.profile ?? "full", model: null });
    }
  }, [health?.profile]);

  const send = () => {
    if (busy) return;
    const req = { text: text.trim(), files, manualId: manuals.length > 0 ? manualId : null };
    setText("");
    setFiles([]);
    void run(req);
  };

  const retry = (id: string) => {
    const req = sent.current.get(id);
    if (req && !busy) void run(req);
  };

  const pick = (example: string, attach?: QuickStart["attach"]) => {
    setText(example);
    const el = fileInput.current;
    if (!el) return;
    el.accept = attach ? PICK_ACCEPT[attach] : ACCEPT;
    if (attach) el.click();
  };

  const onDragOver = (e: DragEvent) => {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    setDragging(true);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length) setFiles([...files, ...dropped]);
  };

  const selected = turns.find((t) => t.id === selectedId) ?? turns[turns.length - 1] ?? null;

  return (
    <div className="ws" onDragOver={onDragOver} onDragLeave={(e) => {
      if (e.currentTarget === e.target || !e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
    }} onDrop={onDrop}>
      <div className="ws__bar">
        <div className="bar__inner">
          <Wordmark />
          <div className="ws__right">
            <span className={`status ${down ? "status--down" : ""}`}
              title="Every model runs on this laptop. Nothing you send leaves it.">
              <span className="status__dot" aria-hidden="true" />
              <span className="status__text">
                {down ? "HomeFix isn't running" : online ? "Private: runs on this laptop" : "Wi-Fi off, still working"}
              </span>
            </span>
            {health && <span className="badge" title="Profile and machine">{health.profile} {MACHINE[health.profile] ?? ""}</span>}
            {IS_MOCK && <span className="badge badge--mock">MOCK</span>}
            {turns.length > 0 && (
              <button type="button" className="btn btn--small" disabled={busy}
                onClick={() => { setTurns([]); setSelectedId(null); }}>
                <Icon as={Plus} size={16} />New question
              </button>
            )}
          </div>
        </div>
      </div>
      <BackendBanner apiUrl={API_LABEL} down={down} />
      <div className="ws__body">
        <Rail turn={selected} />
        <main className="main" id="content">
          {turns.length === 0 ? <StartScreen onPick={pick} />
            : <MessageList turns={turns} onRetry={retry} selectedId={selected?.id ?? null} onSelect={setSelectedId} />}
          <Composer text={text} onText={setText} files={files} onFiles={setFiles} onSend={send} busy={busy} note={note}
            manuals={manuals} manualId={manualId} onManual={setManualId} inputRef={fileInput} />
        </main>
      </div>
      {dragging && <div className="dropzone" aria-hidden="true">Drop to attach</div>}
    </div>
  );
}
