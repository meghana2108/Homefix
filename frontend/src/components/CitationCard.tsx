import type { CitationEvent } from "../contract";

/** The verbatim manual quote, then its page and source file. */
export function CitationCard({ citation }: { citation: CitationEvent }) {
  const where = citation.page === null ? citation.source : `p. ${citation.page} · ${citation.source}`;
  return (
    <figure className="card" aria-label="Citation" style={{ margin: 0 }}>
      <blockquote style={{ margin: 0, overflowWrap: "anywhere" }}>{citation.quote}</blockquote>
      <figcaption className="muted">{where}</figcaption>
    </figure>
  );
}
