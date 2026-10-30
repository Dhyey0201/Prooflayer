"use client";

import { ErrorPanel } from "@/components/ErrorPanel";
import { getBenchmarkReport } from "@/lib/api/client";
import type { BenchmarkRatio, BenchmarkReport } from "@/lib/api/types";
import { useAsyncResource } from "@/lib/api/useAsyncResource";

/** Metrics shown first, in this order; any others in the report follow. */
const LABELS: Record<string, string> = {
  verdict_accuracy: "Verdict accuracy",
  detection_recall: "Detection recall",
  benign_cases_flagged: "Benign cases flagged",
  false_positive_rate: "False-positive rate",
  claim_mismatch_recall: "Claim-mismatch recall",
  claim_accuracy: "Claim-status accuracy",
  integrity_detection_rate: "Integrity detection (with ledger)",
  full_rewrite_detected_without_ledger: "Full rewrite caught without ledger",
  malicious_challenges_blocked: "Malicious challenges blocked",
};

/** A null ratio (denominator 0) is "n/a", never 0. */
export function formatRatio(ratio: BenchmarkRatio): string {
  if (ratio.value === null) return "n/a";
  return `${(ratio.value * 100).toFixed(1).replace(/\.0$/, "")}%`;
}

function formatMs(ms: number | null): string {
  if (ms === null) return "n/a";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

function orderedMetrics(report: BenchmarkReport): [string, BenchmarkRatio][] {
  const known = Object.keys(LABELS).filter((name) => name in report.metrics);
  const rest = Object.keys(report.metrics).filter((name) => !(name in LABELS));
  return [...known, ...rest].map((name) => [name, report.metrics[name]]);
}

export function BenchmarkReportView() {
  const state = useAsyncResource<BenchmarkReport>(() => getBenchmarkReport());

  if (state.phase === "loading") {
    return (
      <p role="status" className="text-sm text-muted">
        Loading the published benchmark report&hellip;
      </p>
    );
  }
  if (state.phase === "error") {
    return (
      <ErrorPanel message={state.message} requestId={state.requestId} onRetry={state.refresh} />
    );
  }

  const report = state.data;
  const env = report.environment;
  const overhead = report.verification_overhead;
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-surface/60 p-4 text-sm">
        <p className="text-foreground">
          {report.seed_count} seeded cases &times; {report.passes} passes, generated{" "}
          <time dateTime={report.generated_at}>{report.generated_at}</time>.
        </p>
        <ul className="mt-2 space-y-1 text-xs text-muted">
          <li>
            Every case met its ground truth:{" "}
            <span className="font-mono text-foreground">
              {report.all_expectations_met ? "yes" : `no (${report.mismatched_cases.join(", ")})`}
            </span>
          </li>
          <li>
            Identical outcomes across passes:{" "}
            <span className="font-mono text-foreground">{report.deterministic ? "yes" : "no"}</span>
          </li>
          <li>
            Secret matches in stored evidence:{" "}
            <span className="font-mono text-foreground">{report.secret_scan.matches}</span>
          </li>
          <li>
            Agent: <span className="font-mono">{env.model.model_id}</span> ({env.model.provider});
            sandbox <span className="font-mono">{env.sandbox.driver}</span>
            {env.sandbox.enforced ? " (enforced)" : " (not enforced)"}; verifier{" "}
            <span className="font-mono">
              {env.verifier.driver}/{env.verifier.isolation}, network {env.verifier.network}
            </span>
          </li>
        </ul>
      </div>

      <section aria-labelledby="metrics-heading" className="space-y-3">
        <h2 id="metrics-heading" className="text-lg font-semibold text-foreground">
          Measured metrics
        </h2>
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {orderedMetrics(report).map(([name, ratio]) => (
            <div key={name} className="rounded-lg border border-border bg-surface/60 p-3">
              <dt className="text-sm font-medium text-foreground">{LABELS[name] ?? name}</dt>
              <dd className="mt-1">
                <span className="font-mono text-xl font-semibold text-foreground">
                  {formatRatio(ratio)}
                </span>{" "}
                <span className="font-mono text-xs text-muted">
                  ({ratio.numerator}/{ratio.denominator})
                </span>
                <p className="mt-1 text-xs text-muted">{ratio.definition}</p>
              </dd>
            </div>
          ))}
          <div className="rounded-lg border border-border bg-surface/60 p-3">
            <dt className="text-sm font-medium text-foreground">Verification overhead</dt>
            <dd className="mt-1">
              <span className="font-mono text-xl font-semibold text-foreground">
                {formatMs(overhead.verification_ms_median)}
              </span>{" "}
              <span className="font-mono text-xs text-muted">
                median, p95 {formatMs(overhead.verification_ms_p95)} (n={overhead.samples})
              </span>
              <p className="mt-1 text-xs text-muted">{overhead.definition}</p>
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="limitations-heading" className="space-y-2">
        <h2 id="limitations-heading" className="text-lg font-semibold text-foreground">
          Read before citing a number
        </h2>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          {report.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
