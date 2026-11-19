import type { CodeResultEvent } from "../contract";

function badgeText(r: CodeResultEvent): string {
  if (r.passed) return `✓ passed ${r.tests_run - r.failures}/${r.tests_run}`;
  if (r.tests_run === 0) return "✕ no examples ran";
  return `✕ failed ${r.failures}/${r.tests_run}`;
}

/** Generated code, a pass/fail badge (in text), the attempt count and the test output. */
export function CodeResultPanel({ result }: { result: CodeResultEvent }) {
  return (
    <section className="card" aria-label="Code result">
      <p>
        <span className={result.passed ? "badge badge--ok" : "badge"} data-passed={result.passed}
          style={result.passed ? undefined : { color: "var(--error-line)", borderColor: "var(--error-line)" }}>
          {badgeText(result)}
        </span>{" "}
        <span className="muted">Attempt {result.attempts} of 2</span>
      </p>
      <pre><code>{result.code}</code></pre>
      <details>
        <summary>Test output</summary>
        <pre>{result.output_tail}</pre>
      </details>
    </section>
  );
}
