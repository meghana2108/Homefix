// STUB from A10. Meghana owns this file and replaces it in M12.
import type { CitationEvent } from "../contract";

export function CitationCard({ citation }: { citation: CitationEvent }) {
  return <pre className="stub">{JSON.stringify(citation, null, 2)}</pre>;
}
