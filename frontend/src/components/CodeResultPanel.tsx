// STUB from A10. Meghana owns this file and replaces it in M12.
import type { CodeResultEvent } from "../contract";

export function CodeResultPanel({ result }: { result: CodeResultEvent }) {
  return <pre className="stub">{JSON.stringify(result, null, 2)}</pre>;
}
