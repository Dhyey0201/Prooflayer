import type { Metadata } from "next";

import { RunsTable } from "@/components/dashboard/RunsTable";
import { SAMPLE_RUNS } from "@/lib/fixtures/runs";

export const metadata: Metadata = {
  title: "Runs — ProofLayer",
};

export default function RunsPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Runs</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Run creation and the persisted run list ship in Commit 03/04. This
          page shows the table shape against clearly labeled sample data.
        </p>
      </header>
      <RunsTable runs={SAMPLE_RUNS} isSample caption="All runs" />
    </div>
  );
}
