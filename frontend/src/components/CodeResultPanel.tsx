import type { CodeResultEvent } from "../contract";

function badgeText(r: CodeResultEvent): string {
  if (r.passed) return `✓ passed ${r.tests_run - r.failures}/${r.tests_run}`;
  if (r.tests_run === 0) return "✕ no examples ran";
  return `✕ failed ${r.failures}/${r.tests_run}`;
}

/** Generated code, a pass/fail badge (in text), the attempt count and the test output. */
export function CodeResultPanel({ result }: { result: CodeResultEvent }) {
  return (
    <section className="card card--code" aria-label="Code result">
      <p className="code__head">
        <span className={`pill ${result.passed ? "pill--ok" : "pill--bad"}`} data-passed={result.passed}>
          {badgeText(result)}
        </span>{" "}
        <span className="muted">Attempt {result.attempts} of 2</span>
        <span className="muted"> · tested in a sandbox</span>
      </p>
      <pre className="code" style={{ overflowX: "auto", maxWidth: "100%" }}><code>{result.code}</code></pre>
      <details>
        <summary>Test output</summary>
        <pre className="code code--out" style={{ overflowX: "auto", maxWidth: "100%" }}>{result.output_tail || "(no output)"}</pre>
      </details>
    </section>
  );
}
