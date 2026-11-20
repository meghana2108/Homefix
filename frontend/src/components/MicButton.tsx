import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { wsUrl } from "../api/client";
import { Icon } from "./Icons";

/** WS /api/mic messages (app/api/mic.py). Not part of the shared SSE contract. */
type MicMessage = { type: "partial"; text: string } | { type: "final"; text: string; speech?: boolean }
  | { type: "error"; message: string };

export const MIC_URL = wsUrl("/api/mic");
const CHUNK_MS = 3000;
const FINAL_TIMEOUT_MS = 60000;

export function micSupported(): boolean {
  return typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
}

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** The recording as a file the chat can take: "audio/webm;codecs=opus" -> mic-sound-<time>.webm, audio/webm. */
function soundFile(chunks: Blob[], mime: string): File {
  const type = (mime || "audio/webm").split(";")[0];
  const ext = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
  const t = new Date().toTimeString().slice(0, 8).replace(/:/g, "");
  return new File(chunks, `mic-sound-${t}.${ext}`, { type });
}

/**
 * 🎤 button: records in 3 s chunks, streams them to /api/mic, reports partial transcripts, and
 * hands over the final text. When the server says it wasn't speech (an alarm, a beep, a drip), it hands
 * over the recording itself instead, so it can be sent as a sound. It never sends a chat message itself.
 */
export function MicButton({ onPartial, onFinal, onSound, disabled = false }: {
  onPartial: (text: string) => void;
  onFinal: (text: string) => void;
  onSound?: (file: File) => void;
  disabled?: boolean;
}) {
  const [state, setState] = useState<"idle" | "starting" | "recording" | "finishing">("idle");
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const ws = useRef<WebSocket | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const done = useRef(false);
  const chunks = useRef<Blob[]>([]);
  const mime = useRef("");
  const timers = useRef<number[]>([]);
  // latest callbacks, so text typed while recording isn't lost when the final arrives
  const cb = useRef({ onPartial, onFinal, onSound });
  cb.current = { onPartial, onFinal, onSound };

  const cleanup = () => {
    timers.current.forEach((t) => window.clearInterval(t));
    timers.current = [];
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (rec.current && rec.current.state !== "inactive") {
      rec.current.onstop = null;
      rec.current.stop();
    }
    rec.current = null;
    if (ws.current && ws.current.readyState <= 1) ws.current.close();
    ws.current = null;
    setState("idle");
  };

  useEffect(() => () => { done.current = true; cleanup(); }, []);  // stop the mic if the page goes away

  const fail = (msg: string) => {
    done.current = true;
    setError(msg);
    cb.current.onPartial("");
    cleanup();
  };

  const start = async () => {
    setError(null);
    done.current = false;
    setState("starting");
    let media: MediaStream;
    try {
      media = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      fail("Allow the microphone for this page, then try again.");
      return;
    }
    if (done.current) {  // cancelled while waiting for the permission prompt
      media.getTracks().forEach((t) => t.stop());
      return;
    }
    stream.current = media;
    const socket = new WebSocket(MIC_URL);
    ws.current = socket;
    socket.onmessage = (e) => {
      let msg: MicMessage;
      try {
        msg = JSON.parse(String(e.data)) as MicMessage;
      } catch {
        return;
      }
      if (msg.type === "partial") cb.current.onPartial(msg.text);
      else if (msg.type === "final") {
        done.current = true;
        cb.current.onPartial("");
        const recorded = chunks.current.reduce((n, c) => n + c.size, 0) > 0;
        if (msg.speech === false && recorded && cb.current.onSound) cb.current.onSound(soundFile(chunks.current, mime.current));
        else cb.current.onFinal(msg.text);
        cleanup();
      } else if (msg.type === "error") fail(msg.message);
    };
    socket.onerror = () => {};
    socket.onclose = () => { if (!done.current) fail(`Can't reach the live mic at ${MIC_URL}. Is the server running?`); };
    socket.onopen = () => {
      const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((t) => MediaRecorder.isTypeSupported?.(t));
      const r = new MediaRecorder(media, type ? { mimeType: type } : undefined);
      rec.current = r;
      chunks.current = [];
      mime.current = r.mimeType || type || "";
      r.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunks.current.push(ev.data);  // kept, in case it turns out to be a sound
        if (ev.data.size > 0 && socket.readyState === WebSocket.OPEN) socket.send(ev.data);
      };
      r.onstop = () => { if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "stop" })); };
      r.start(CHUNK_MS);
      setSeconds(0);
      timers.current.push(window.setInterval(() => setSeconds((s) => s + 1), 1000));
      setState("recording");
    };
  };

  const stop = () => {
    setState("finishing");
    stream.current?.getTracks().forEach((t) => t.stop());
    rec.current?.stop();  // its last chunk goes out, then onstop sends {"type":"stop"}
    timers.current.forEach((t) => window.clearInterval(t));
    timers.current = [window.setTimeout(() => { if (!done.current) fail("The transcript took too long. Try again."); }, FINAL_TIMEOUT_MS)];
  };

  if (!micSupported()) return null;
  return (
    <span className="mic">
      {state === "recording" ? (
        <button type="button" className="btn btn--icon mic--on" aria-label="Stop the mic" onClick={stop}>
          <Icon as={Square} size={14} />{clock(seconds)}
        </button>
      ) : state === "finishing" ? (
        <button type="button" className="btn btn--icon" aria-label="Transcribing…" disabled>
          <span className="spinner" aria-hidden="true" />
        </button>
      ) : state === "starting" ? (
        // getUserMedia can wait forever on an unanswered permission prompt: let the user back out
        <button type="button" className="btn btn--icon" aria-label="Cancel the mic" title="Waiting for the microphone… click to cancel"
          onClick={() => { done.current = true; cleanup(); }}>
          <span className="spinner" aria-hidden="true" />
        </button>
      ) : (
        <button type="button" className="btn btn--icon" aria-label="Start the mic" title="Speak your question, or record a sound (an alarm, a beep, a drip)"
          disabled={disabled} onClick={() => void start()}>
          <Icon as={Mic} />
        </button>
      )}
      {error && <span className="mic__error" role="alert">{error}</span>}
    </span>
  );
}
