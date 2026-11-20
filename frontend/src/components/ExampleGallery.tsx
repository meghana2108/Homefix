import { BadgeCheck, BookOpen, FileText, HelpCircle, MessageCircleQuestion, OctagonAlert, PenLine, Play, Wrench } from "lucide-react";
import { useState } from "react";
import type { Manual } from "../contract";
import { EXAMPLE_KINDS, ordered, type Example, type ExampleKind } from "../examples";
import { Icon } from "./Icons";

const ROLE = {
  fix: { label: "Problem → fix", icon: Wrench },
  question: { label: "Question", icon: HelpCircle },
  asks: { label: "Asks you back", icon: MessageCircleQuestion },
  stop: { label: "Danger → stop", icon: OctagonAlert },
} as const;

/** A sample file, shown the way it will appear in the conversation. */
function Preview({ ex }: { ex: Example }) {
  if (!ex.file) return null;
  const src = `/samples/${ex.file}`;
  if (ex.preview === "image") return <img className="ex__img" src={src} alt={ex.fileLabel} loading="lazy" />;
  if (ex.preview === "audio") return <audio className="ex__audio" src={src} controls preload="none" aria-label={ex.fileLabel} />;
  if (ex.preview === "video") return <video className="ex__video" src={src} muted controls preload="metadata" aria-label={ex.fileLabel} />;
  return <span className="file"><Icon as={FileText} size={14} />{ex.fileLabel}</span>;
}

/** Ready-made examples for every kind of question, one click each. Every one was run on the 8 GB Mac. */
export function ExampleGallery({ onTry, busy, manuals }: {
  onTry: (ex: Example) => void; busy: boolean; manuals: Manual[];
}) {
  const [kind, setKind] = useState<ExampleKind>(EXAMPLE_KINDS[0].id);
  const shown = ordered(kind);
  const tab = EXAMPLE_KINDS.find((k) => k.id === kind)!;
  return (
    <section className="gallery" aria-labelledby="gallery-h">
      <h2 id="gallery-h" className="gallery__h">Try an example</h2>
      <p className="gallery__sub">Problems and their fixes first, then plain questions, then ones where HomeFix asks you back. Real photos, recordings and documents before ones we made. One click each.</p>
      <div className="tabs" role="tablist" aria-label="Kinds of question">
        {EXAMPLE_KINDS.map((k) => (
          <button key={k.id} type="button" role="tab" id={`tab-${k.id}`} aria-selected={k.id === kind}
            aria-controls="gallery-panel" className={`tab ${k.id === kind ? "tab--on" : ""}`} onClick={() => setKind(k.id)}>
            <Icon as={k.icon} size={16} />{k.label}
          </button>
        ))}
      </div>
      <div id="gallery-panel" role="tabpanel" aria-labelledby={`tab-${kind}`}>
        <p className="gallery__what">{tab.what}</p>
        <ul className="examples-grid">
          {shown.map((ex) => (
            <li key={ex.id} className="ex">
              <p className={`ex__role ex__role--${ex.role}`}><Icon as={ROLE[ex.role].icon} size={14} />{ROLE[ex.role].label}</p>
              <Preview ex={ex} />
              {ex.source && (
                <p className={`ex__src ${ex.source.real ? "ex__src--real" : ""}`}>
                  <Icon as={ex.source.real ? BadgeCheck : PenLine} size={14} />{ex.source.credit}
                </p>
              )}
              <p className="ex__q">“{ex.question}”</p>
              <p className="ex__see">{ex.see}</p>
              <button type="button" className="btn btn--small ex__try" disabled={busy} onClick={() => onTry(ex)}
                aria-label={`Try it: ${ex.question}`}>
                <Icon as={Play} size={14} />Try it
              </button>
            </li>
          ))}
        </ul>
        {kind === "manual" && manuals.length > 0 && (
          <div className="shelf">
            <p className="shelf__h"><Icon as={BookOpen} size={16} />Manuals HomeFix can read now</p>
            <ul>
              {manuals.map((m) => <li key={m.id}>{m.title} <span className="faint">({m.pages} {m.pages === 1 ? "page" : "pages"})</span></li>)}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
