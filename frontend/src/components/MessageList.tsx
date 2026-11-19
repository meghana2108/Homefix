import { useEffect, useRef } from "react";
import type { Turn } from "../state/reduce";
import { TurnView } from "./TurnView";

export function MessageList({ turns, onRetry }: { turns: Turn[]; onRetry: (id: string) => void }) {
  const end = useRef<HTMLDivElement>(null);
  const last = turns[turns.length - 1];
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [turns.length, last?.answer, last?.statuses.length, last?.final]);
  return (
    <div className="messages" aria-live="polite">
      {turns.map((t) => <TurnView key={t.id} turn={t} onRetry={() => onRetry(t.id)} />)}
      <div ref={end} />
    </div>
  );
}
