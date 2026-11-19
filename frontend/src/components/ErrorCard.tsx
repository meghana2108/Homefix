import { CircleX, RotateCcw } from "lucide-react";
import type { ErrorEvent } from "../contract";
import { Icon } from "./Icons";

export function ErrorCard({ error, onRetry }: { error: ErrorEvent; onRetry?: () => void }) {
  return (
    <div className="card card--error" role="alert">
      <p className="card__title"><Icon as={CircleX} />Something went wrong</p>
      <p>{error.message}</p>
      {error.retryable && onRetry && (
        <button type="button" className="btn btn--small" onClick={(e) => { e.stopPropagation(); onRetry(); }}>
          <Icon as={RotateCcw} size={16} />Try again
        </button>
      )}
    </div>
  );
}
