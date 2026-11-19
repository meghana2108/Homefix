export function formatSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}

export function LatencyBadge({ latencyMs, model }: { latencyMs: number; model: string | null }) {
  return (
    <span className="latency" title={model ? `Model: ${model}` : "No model ran"}>
      ⏱ {formatSeconds(latencyMs)}
    </span>
  );
}
