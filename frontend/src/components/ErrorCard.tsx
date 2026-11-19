import type { ErrorEvent } from "../contract";

export function ErrorCard({ error, onRetry }: { error: ErrorEvent; onRetry?: () => void }) {
  return (
    <div className="card card--error" role="alert">
      <p>{error.message}</p>
      {error.retryable && onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
