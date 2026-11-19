import { useEffect, useRef } from "react";
import type { Turn } from "../state/reduce";
import { TurnView } from "./TurnView";

export function MessageList({ turns, onRetry, selectedId = null, onSelect }: {
  turns: Turn[]; onRetry: (id: string) => void; selectedId?: string | null; onSelect?: (id: string) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  const last = turns[turns.length - 1];
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [turns.length, last?.answer, last?.statuses.length, last?.final]);
  return (
    <div className="messages" aria-live="polite">
      <div className="thread">
        {turns.map((t) => (
          <TurnView key={t.id} turn={t} onRetry={() => onRetry(t.id)} selected={t.id === selectedId}
            onSelect={onSelect ? () => onSelect(t.id) : undefined} />
        ))}
      </div>
      <div ref={end} />
    </div>
  );
}
