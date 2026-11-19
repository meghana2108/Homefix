import type { RefusalEvent } from "../contract";

export function RefusalCard({ refusal }: { refusal: RefusalEvent }) {
  if (refusal.reason === "safety") {
    return (
      <div className="card card--safety" role="alert">
        <p>{refusal.message}</p>
      </div>
    );
  }
  return (
    <div className="card card--refusal" role="status">
      <p>{refusal.message}</p>
    </div>
  );
}
