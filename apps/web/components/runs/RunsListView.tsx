"use client";

import { ErrorPanel } from "@/components/ErrorPanel";
import { RunsTable } from "@/components/dashboard/RunsTable";
import { useRuns } from "@/lib/api/useRuns";

export function RunsListView() {
  const runs = useRuns(50);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Runs</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Every run persisted by the backend, newest first. Click a run to
          open its trace timeline.
        </p>
      </header>
      {runs.phase === "loading" && (
        <p role="status" className="text-sm text-muted">
          Loading runs&hellip;
        </p>
      )}
      {runs.phase === "error" && (
        <ErrorPanel
          message={runs.message}
          requestId={runs.requestId}
          onRetry={runs.refresh}
        />
      )}
      {runs.phase === "ready" && <RunsTable runs={runs.data} caption="All runs" />}
    </div>
  );
}
