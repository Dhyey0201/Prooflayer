import type { Metadata } from "next";

import { BenchmarkReportView } from "@/components/benchmark/BenchmarkReportView";

export const metadata: Metadata = {
  title: "Benchmark — ProofLayer",
};

export default function BenchmarkPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Benchmark</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          The deterministic benchmark harness runs each seeded case (true pass, false success,
          denied access, attempted exfiltration, corrupted log, malformed model output and more)
          through the real run pipeline and independent verifier. Every number below is read
          from the published report, with its numerator and denominator; formulas are in{" "}
          <code className="rounded bg-background px-1 py-0.5 text-xs">
            docs/04_TEST_EVALUATION.md
          </code>{" "}
          and limitations in{" "}
          <code className="rounded bg-background px-1 py-0.5 text-xs">
            docs/07_BENCHMARK_LIMITATIONS.md
          </code>
          .
        </p>
      </header>
      <BenchmarkReportView />
    </div>
  );
}
