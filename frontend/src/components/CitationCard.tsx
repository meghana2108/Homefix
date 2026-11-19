import { BookOpenCheck } from "lucide-react";
import { useState } from "react";
import type { CitationEvent } from "../contract";
import { Icon } from "./Icons";

export const QUOTE_FOLD = 320;

/** The verbatim manual quote, then its page and source file. */
export function CitationCard({ citation }: { citation: CitationEvent }) {
  const where = citation.page === null ? citation.source : `p. ${citation.page} · ${citation.source}`;
  const [open, setOpen] = useState(false);
  const long = citation.quote.length > QUOTE_FOLD;
  const shown = long && !open ? `${citation.quote.slice(0, QUOTE_FOLD).replace(/\s+\S*$/, "")} …` : citation.quote;
  return (
    <figure className="evidence" aria-label="Citation" style={{ margin: 0 }}>
      <p className="evidence__label"><Icon as={BookOpenCheck} size={16} />Word for word from the document</p>
      <div className="card card--citation">
        <blockquote style={{ margin: 0, overflowWrap: "anywhere" }}>{shown}</blockquote>
        {long && (
          <button type="button" className="linkbtn" aria-expanded={open} onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}>
            {open ? "Show less" : "Show the full quote"}
          </button>
        )}
        <figcaption>{where}</figcaption>
      </div>
    </figure>
  );
}
