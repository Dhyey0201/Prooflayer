import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Benchmark — ProofLayer",
};

const METRICS: { name: string; definition: string }[] = [
  {
    name: "Detection recall",
    definition: "True policy violations flagged ÷ all seeded policy violations.",
  },
  {
    name: "False-positive rate",
    definition: "Benign operations blocked ÷ all benign operations.",
  },
  {
    name: "Claim-mismatch recall",
    definition: "Unsupported/false completion claims caught ÷ all ground-truth false claims.",
  },
  {
    name: "Verdict accuracy",
    definition: "Correct run-level verdicts ÷ all seeded runs.",
  },
  {
    name: "Verification overhead",
    definition: "(agent + proof time) − agent-only time, reported as median and p95.",
  },
  {
    name: "Integrity detection",
    definition: "Altered logs detected ÷ mutated logs in fixture tests.",
  },
];

export default function BenchmarkPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Benchmark</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          A deterministic benchmark harness (12&ndash;20 seeded cases, including true pass,
          false success, denied access, attempted exfiltration, corrupted log and malformed
          model output) measures these metrics automatically.
        </p>
      </header>

      <div className="rounded-xl border border-dashed border-border p-6">
        <p className="text-sm font-medium text-foreground">No benchmark results yet</p>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          The harness itself (backend, Commit 13 in{" "}
          <code className="rounded bg-background px-1 py-0.5 text-xs">
            docs/03_SEVEN_DAY_COMMIT_PLAN.md
          </code>
          ) hasn&apos;t merged yet, so there is no measured data to show. This page will
          render its real output once that CLI publishes a report &mdash; no number below is
          real; showing one before it is actually measured would be exactly the kind of
          fabricated UI value this project exists to catch.
        </p>
      </div>

      <section aria-labelledby="metrics-heading" className="space-y-3">
        <h2 id="metrics-heading" className="text-lg font-semibold text-foreground">
          Metrics this page will report
        </h2>
        <p className="text-sm text-muted">
          Defined in{" "}
          <code className="rounded bg-background px-1 py-0.5 text-xs">
            docs/04_TEST_EVALUATION.md
          </code>
          .
        </p>
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {METRICS.map((metric) => (
            <div key={metric.name} className="rounded-lg border border-border bg-surface/60 p-3">
              <dt className="text-sm font-medium text-foreground">{metric.name}</dt>
              <dd className="mt-1 text-xs text-muted">{metric.definition}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
