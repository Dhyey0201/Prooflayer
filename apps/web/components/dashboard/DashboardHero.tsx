"use client";

import Link from "next/link";

import { formatRatio } from "@/components/benchmark/BenchmarkReportView";
import { getBenchmarkReport } from "@/lib/api/client";
import type { BenchmarkReport } from "@/lib/api/types";
import { useAsyncResource } from "@/lib/api/useAsyncResource";

const STEPS = [
  {
    title: "Claim",
    body: "The agent works in a policy-scoped sandbox and reports what it did. Its claim is recorded as untrusted input.",
  },
  {
    title: "Challenge",
    body: "A separate, network-less verifier re-runs the pinned checks. The model can also propose a new test, which is validated and executed.",
  },
  {
    title: "Evidence",
    body: "Every step lands in a hash-chained log, and the certificate ties the verdict to measurements anyone can re-check offline.",
  },
] as const;

/**
 * Headline numbers, read from the published report; hidden if none is published.
 * Detection recall is included on purpose: it is the one metric with a miss.
 */
const HEADLINE: { metric: string; label: string }[] = [
  { metric: "verdict_accuracy", label: "verdict accuracy" },
  { metric: "detection_recall", label: "policy violations flagged" },
  { metric: "claim_mismatch_recall", label: "false claims caught" },
  { metric: "integrity_detection_rate", label: "tampering detected" },
];

function MeasuredStats() {
  const report = useAsyncResource<BenchmarkReport>(() => getBenchmarkReport());
  if (report.phase !== "ready") return null;
  const stats = HEADLINE.filter(({ metric }) => metric in report.data.metrics);
  if (stats.length === 0) return null;
  return (
    <div className="mt-8">
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map(({ metric, label }) => {
          const ratio = report.data.metrics[metric];
          return (
            <div
              key={metric}
              className="rounded-xl border border-border bg-background/60 px-4 py-3 backdrop-blur"
            >
              <dd className="font-mono text-2xl font-semibold text-foreground">
                {formatRatio(ratio)}
              </dd>
              <dt className="mt-0.5 text-xs text-muted">
                {label}{" "}
                <span className="font-mono">
                  ({ratio.numerator}/{ratio.denominator})
                </span>
              </dt>
            </div>
          );
        })}
      </dl>
      <p className="mt-2 text-xs text-muted">
        Measured on {report.data.seed_count} seeded cases &times; {report.data.passes} passes
        with the real verifier.{" "}
        <Link href="/benchmark" className="text-accent hover:underline">
          Method and limitations
        </Link>
      </p>
    </div>
  );
}

export function DashboardHero() {
  return (
    <header className="relative overflow-hidden rounded-2xl border border-border bg-surface/70 p-6 sm:p-10">
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-accent/20 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-emerald-500/10 blur-3xl"
      />
      <div className="relative">
        <p className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
          <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
          AI agent outcome verification
        </p>
        <h1 className="mt-4 max-w-3xl text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          An agent saying{" "}
          <span className="bg-gradient-to-r from-sky-300 to-emerald-300 bg-clip-text text-transparent">
            &ldquo;all tests passed&rdquo;
          </span>{" "}
          is not proof.
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted sm:text-base">
          ProofLayer independently checks what an AI coding agent claims it did, and issues a
          certificate backed by evidence the agent cannot fabricate.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a
            href="#scenarios-heading"
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-background transition hover:brightness-110"
          >
            Try a scenario
          </a>
          <Link
            href="/runs"
            className="rounded-lg border border-border bg-background/40 px-4 py-2 text-sm font-medium text-foreground transition hover:border-accent/50"
          >
            Browse recorded runs
          </Link>
        </div>
        <MeasuredStats />
      </div>

      <ol className="relative mt-10 grid grid-cols-1 gap-3 md:grid-cols-3">
        {STEPS.map((step, index) => (
          <li key={step.title} className="rounded-xl border border-border bg-background/50 p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent/15 font-mono text-xs text-accent">
                {index + 1}
              </span>
              {step.title}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-muted">{step.body}</p>
          </li>
        ))}
      </ol>
    </header>
  );
}
