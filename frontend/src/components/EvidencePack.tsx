import { CircleCheck, CircleX, ClipboardCheck, Copy, FileSearch, Printer, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { buildEvidence, checkFile, sha256, type Evidence, type FileCheck } from "../state/evidence";
import type { Turn } from "../state/reduce";
import { Icon } from "./Icons";

const size = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`);

/** The repair request for one answer: dated, every file fingerprinted, the verified quote, the danger check,
 *  and an editable letter. Print or save as PDF. Built in the browser; nothing leaves the laptop. */
export function EvidencePack({ turn, files, onClose }: { turn: Turn; files: File[]; onClose: () => void }) {
  const [ev, setEv] = useState<Evidence | null>(null);
  const [letter, setLetter] = useState("");
  const [fingerprint, setFingerprint] = useState("");
  const [copied, setCopied] = useState(false);
  const [check, setCheck] = useState<FileCheck | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let alive = true;
    void buildEvidence(turn, files).then((e) => {
      if (!alive) return;
      setEv(e);
      setLetter(e.letter);
      setFingerprint(e.fingerprint);
    });
    return () => { alive = false; };
  }, [turn, files]);

  // the fingerprint follows the letter as it's edited
  useEffect(() => {
    if (!ev) return;
    let alive = true;
    const { fingerprint: _old, ...rest } = ev;
    void sha256(JSON.stringify({ ...rest, letter })).then((h) => alive && setFingerprint(h));
    return () => { alive = false; };
  }, [ev, letter]);

  useEffect(() => {
    document.documentElement.classList.add("evidence-open");
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => {
      document.documentElement.classList.remove("evidence-open");
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(letter);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return createPortal(
    <div className="evidence-layer" role="dialog" aria-modal="true" aria-labelledby="evidence-h">
      <div className="evidence-sheet">
        <header className="evidence__head">
          <div>
            <h2 id="evidence-h" className="evidence__title"><Icon as={ClipboardCheck} size={20} />Repair request</h2>
            <p className="evidence__meta">{ev ? ev.madeAt : "Preparing…"} · Made on this laptop. Nothing was uploaded.</p>
          </div>
          <button ref={closeRef} type="button" className="btn btn--icon no-print" aria-label="Close the repair request" onClick={onClose}>
            <Icon as={X} />
          </button>
        </header>

        {!ev ? <p className="live"><span className="spinner" aria-hidden="true" />Fingerprinting your files…</p> : (
          <>
            <section className="evidence__sec">
              <h3>What you asked</h3>
              <p>{ev.question || "(no message)"}</p>
            </section>

            {ev.files.length > 0 && (
              <section className="evidence__sec">
                <h3>Your files and their fingerprints</h3>
                <ul className="evidence__files">
                  {ev.files.map((f) => {
                    const url = turn.sentFiles.find((s) => s.name === f.name && s.kind === "image")?.url;
                    return (
                      <li key={f.name}>
                        {url && <img src={url} alt={f.name} className="evidence__thumb" />}
                        <div>
                          <p><strong>{f.name}</strong> <span className="faint">({f.kind}, {size(f.bytes)})</span></p>
                          <p className="mono evidence__hash">SHA-256 {f.sha256 || "not available in this browser"}</p>
                        </div>
                      </li>
                    );
                  })}
                </ul>
                <p className="faint evidence__note">A fingerprint changes if even one pixel or byte of the file changes, so anyone can check the file you send is this one.</p>
              </section>
            )}

            {ev.files.length > 0 && (
              <section className="evidence__sec no-print">
                <h3>Check a file</h3>
                <label className="btn btn--small evidence__pick">
                  <Icon as={FileSearch} size={16} />Check a file against this request
                  <input type="file" className="sr-only" aria-label="Check a file against this request"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      e.target.value = "";
                      if (f) void checkFile(f, ev.files).then(setCheck);
                    }} />
                </label>
                <p className="faint evidence__note">Pick the photo you sent, or one someone sends back. It's checked here, offline.</p>
                {check && (
                  <div role="status" className={`evidence__check ${check.ok ? "evidence__check--ok" : "evidence__check--bad"}`}>
                    <p className="evidence__check-title">
                      <Icon as={check.ok ? CircleCheck : CircleX} size={18} />
                      {check.ok
                        ? `Matches ${check.match.name}: not changed.`
                        : "Doesn't match any file in this request. It has been changed, or it's a different file."}
                    </p>
                    {!check.ok && check.sameName && (
                      <p>It has the same name as {check.sameName.name} in this request, but different contents.</p>
                    )}
                    <p className="mono evidence__hash">{check.name}: SHA-256 {check.sha256}</p>
                    {!check.ok && check.sameName && <p className="mono evidence__hash">In this request: SHA-256 {check.sameName.sha256}</p>}
                  </div>
                )}
              </section>
            )}

            <section className="evidence__sec">
              <h3>What HomeFix found</h3>
              <p>{ev.found || "No answer."}</p>
            </section>

            {ev.quote && (
              <section className="evidence__sec">
                <h3>Word for word from {ev.quote.source}{ev.quote.page != null ? `, page ${ev.quote.page}` : ""}</h3>
                <blockquote className="evidence__quote">{ev.quote.text}</blockquote>
                <p className="faint evidence__note">Checked: this sentence is in the document.</p>
              </section>
            )}

            <section className="evidence__sec">
              <h3>Danger check</h3>
              <p>{ev.danger}</p>
            </section>

            <section className="evidence__sec">
              <h3><label htmlFor="evidence-letter">Letter to your landlord</label></h3>
              <textarea id="evidence-letter" className="evidence__letter" value={letter} rows={10}
                onChange={(e) => { setLetter(e.target.value); setCopied(false); }} />
              <pre className="evidence__letter-print" aria-hidden="true">{letter}</pre>
            </section>

            <footer className="evidence__foot">
              <p className="mono evidence__hash">Pack fingerprint (SHA-256) {fingerprint}</p>
              <div className="evidence__actions no-print">
                <button type="button" className="btn" onClick={() => void copy()}>
                  <Icon as={Copy} size={16} />{copied ? "Copied" : "Copy the letter"}
                </button>
                <button type="button" className="btn btn--primary" onClick={() => window.print()}>
                  <Icon as={Printer} size={16} />Print or save as PDF
                </button>
              </div>
            </footer>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
