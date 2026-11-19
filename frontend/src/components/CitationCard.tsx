import { useState } from "react";
import type { CitationEvent } from "../contract";

export const QUOTE_FOLD = 320;

/** The verbatim manual quote, then its page and source file. */
export function CitationCard({ citation }: { citation: CitationEvent }) {
  const where = citation.page === null ? citation.source : `p. ${citation.page} · ${citation.source}`;
  const [open, setOpen] = useState(false);
  const long = citation.quote.length > QUOTE_FOLD;
  const shown = long && !open ? `${citation.quote.slice(0, QUOTE_FOLD).replace(/\s+\S*$/, "")} …` : citation.quote;
  return (
    <figure className="card card--citation" aria-label="Citation" style={{ margin: 0 }}>
      <p className="result__label"><span aria-hidden="true">📖 </span>Word for word from the document</p>
      <blockquote style={{ margin: 0, overflowWrap: "anywhere" }}>{shown}</blockquote>
      {long && (
        <button type="button" className="linkbtn" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? "Show less" : "Show the full quote"}
        </button>
      )}
      <figcaption className="muted">{where}</figcaption>
    </figure>
  );
}
