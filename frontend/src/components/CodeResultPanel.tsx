import { CircleCheck, CircleX } from "lucide-react";
import type { CodeResultEvent } from "../contract";
import { Icon } from "./Icons";

function badgeText(r: CodeResultEvent): string {
  if (r.passed) return `Passed ${r.tests_run - r.failures} of ${r.tests_run}`;
  if (r.tests_run === 0) return "No examples ran";
  return `Failed ${r.failures} of ${r.tests_run}`;
}

/** Generated code, a pass/fail badge (icon and words), the attempt count and the test output. */
export function CodeResultPanel({ result }: { result: CodeResultEvent }) {
  return (
    <section className="card card--code" aria-label="Code result">
      <p className="code__head">
        <span className={`pill ${result.passed ? "pill--ok" : "pill--bad"}`} data-passed={result.passed}>
          <Icon as={result.passed ? CircleCheck : CircleX} size={14} />{badgeText(result)}
        </span>{" "}
        <span className="faint">Attempt {result.attempts} of 2, tested in a sandbox</span>
      </p>
      <pre className="code" style={{ overflowX: "auto", maxWidth: "100%" }}><code>{result.code}</code></pre>
      <details>
        <summary>Test output</summary>
        <pre className="code code--out" style={{ overflowX: "auto", maxWidth: "100%" }}>{result.output_tail || "(no output)"}</pre>
      </details>
    </section>
  );
}
