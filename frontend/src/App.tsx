import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { API_LABEL, IS_MOCK, getHealth, getManuals, streamChat } from "./api/client";
import { BackendBanner } from "./components/BackendBanner";
import { ACCEPT, Composer, MAX_FILES } from "./components/Composer";
import { Logo } from "./components/Logo";
import { AUTO } from "./components/ManualPicker";
import { MessageList } from "./components/MessageList";
import { WelcomeTiles, type Scenario } from "./components/WelcomeTiles";
import type { Health, HomeFixEvent, Manual } from "./contract";
import { kindOf, newTurn, reduce, type SentFile, type Turn } from "./state/reduce";

const HEALTH_EVERY_MS = 5000;
const TOO_MANY = `Attach up to ${MAX_FILES} files at a time.`;
const MACHINE: Record<string, string> = { full: "M4", lite: "M2" };
const PICK_ACCEPT: Record<NonNullable<Scenario["attach"]>, string> = {
  image: "image/*,.heic,.heif", audio: "audio/*", video: "video/*", document: ".pdf,.docx,.txt,.md",
};

function sentFiles(files: File[]): SentFile[] {
  const canPreview = typeof URL !== "undefined" && typeof URL.createObjectURL === "function";
  return files.map((f) => {
    const kind = kindOf(f.name, f.type);
    return { name: f.name, kind, url: canPreview && kind !== "file" ? URL.createObjectURL(f) : null };
  });
}

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

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([]);
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
      // The stream broke or the server is down: end the turn so Send works again.
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

  const pick = (example: string, attach?: Scenario["attach"]) => {
    setText(example);
    const el = fileInput.current;
    if (attach && el) {
      el.accept = PICK_ACCEPT[attach];
      el.click();
    } else if (el) {
      el.accept = ACCEPT;
    }
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

  return (
    <div className="app" onDragOver={onDragOver} onDragLeave={(e) => {
      if (e.currentTarget === e.target || !e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
    }} onDrop={onDrop}>
      <header className="header">
        <div className="brand">
          <Logo size={30} />
          <div>
            <h1>HomeFix</h1>
            <p className="brand__tag">Help for your first apartment</p>
          </div>
        </div>
        <div className="badges">
          <span className={`privacy ${online ? "" : "privacy--offline"}`}
            title="Every model runs on this laptop. Nothing you send leaves it.">
            {online ? "🔒 Private · runs on this laptop" : "✈️ Wi-Fi off · still working"}
          </span>
          {health && <span className="badge" title="Profile and machine">{health.profile} · {MACHINE[health.profile] ?? "?"}</span>}
          {IS_MOCK && <span className="badge badge--mock">MOCK</span>}
        </div>
      </header>
      <BackendBanner apiUrl={API_LABEL} down={down} />

      <main className="main">
        {turns.length === 0 ? <WelcomeTiles onPick={pick} /> : <MessageList turns={turns} onRetry={retry} />}
        <Composer text={text} onText={setText} files={files} onFiles={setFiles} onSend={send} busy={busy} note={note}
          manuals={manuals} manualId={manualId} onManual={setManualId} inputRef={fileInput} />
      </main>
      {dragging && <div className="dropzone" aria-hidden="true">Drop to attach</div>}
    </div>
  );
}
