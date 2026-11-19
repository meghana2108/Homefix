import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { API_LABEL, IS_MOCK, getHealth, getManuals, streamChat } from "./api/client";
import { BackendBanner } from "./components/BackendBanner";
import { Composer, MAX_FILES } from "./components/Composer";
import { ManualPicker } from "./components/ManualPicker";
import { MessageList } from "./components/MessageList";
import { WelcomeTiles } from "./components/WelcomeTiles";
import type { Health, HomeFixEvent, Manual } from "./contract";
import { newTurn, reduce, type Turn } from "./state/reduce";

const HEALTH_EVERY_MS = 5000;
const TOO_MANY = `Attach up to ${MAX_FILES} files at a time.`;
const MACHINE: Record<string, string> = { full: "M4", lite: "M2" };

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
  const [manualId, setManualId] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [dragging, setDragging] = useState(false);
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
    if (manualId && !manuals.some((m) => m.id === manualId)) setManualId(null);
  }, [manuals, manualId]);

  const setFiles = (next: File[]) => {
    setNote(next.length > MAX_FILES ? TOO_MANY : null);
    setFilesRaw(next.slice(0, MAX_FILES));
  };

  const busy = turns.length > 0 && turns[turns.length - 1].final === null;

  const run = useCallback(async (req: Sent) => {
    const turn = newTurn(req.text, req.files.map((f) => f.name));
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
    const req = { text: text.trim(), files, manualId };
    setText("");
    setFiles([]);
    void run(req);
  };

  const retry = (id: string) => {
    const req = sent.current.get(id);
    if (req && !busy) void run(req);
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
        <h1>HomeFix</h1>
        <div className="badges">
          {health && <span className="badge">{health.profile} · {MACHINE[health.profile] ?? "?"}</span>}
          <span className={`badge ${online ? "" : "badge--ok"}`}>{online ? "Online" : "Wi-Fi off ✓"}</span>
          {IS_MOCK && <span className="badge badge--mock">MOCK</span>}
          {manuals.length > 0 && (
            <button type="button" className="btn btn--small drawer-toggle" aria-expanded={drawer}
              onClick={() => setDrawer((d) => !d)}>Manuals</button>
          )}
        </div>
      </header>
      <BackendBanner apiUrl={API_LABEL} down={down} />

      <div className="layout">
        {manuals.length > 0 && (
          <aside className={`sidebar ${drawer ? "sidebar--open" : ""}`}>
            <ManualPicker manuals={manuals} value={manualId} onChange={(id) => { setManualId(id); setDrawer(false); }} />
          </aside>
        )}
        <main className="main">
          {turns.length === 0 ? <WelcomeTiles onPick={setText} /> : <MessageList turns={turns} onRetry={retry} />}
          <Composer text={text} onText={setText} files={files} onFiles={setFiles} onSend={send} busy={busy} note={note} />
        </main>
      </div>
      {dragging && <div className="dropzone" aria-hidden="true">Drop to attach</div>}
    </div>
  );
}
