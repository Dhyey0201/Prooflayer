"use client";

import { ErrorPanel } from "@/components/ErrorPanel";
import { RunsTable } from "@/components/dashboard/RunsTable";
import { ScenarioCard } from "@/components/dashboard/ScenarioCard";
import { SystemStatusPanel } from "@/components/dashboard/SystemStatusPanel";
import { useRuns } from "@/lib/api/useRuns";
import { useTemplates } from "@/lib/api/useTemplates";

export default function DashboardPage() {
  const templates = useTemplates();
  const runs = useRuns(5);

  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          ProofLayer independently verifies what an AI coding agent claims it
          did. Pick a bounded scenario, watch the sandbox, and challenge the
          completion claim with evidence the agent cannot fabricate.
        </p>
      </header>

      <SystemStatusPanel />

      <section aria-labelledby="scenarios-heading" className="space-y-4">
        <div>
          <h2 id="scenarios-heading" className="text-lg font-semibold text-foreground">
            Scenarios
          </h2>
          <p className="text-sm text-muted">
            Three pre-seeded fixtures the demo replays end to end. Launching a
            run queues it; the backend worker runs the agent in a sandbox. Until
            the independent verifier exists, a finished run concludes
            <code>inconclusive</code>.
          </p>
        </div>
        {templates.phase === "loading" && (
          <p role="status" className="text-sm text-muted">
            Loading scenarios&hellip;
          </p>
        )}
        {templates.phase === "error" && (
          <ErrorPanel
            message={templates.message}
            requestId={templates.requestId}
            onRetry={templates.refresh}
          />
        )}
        {templates.phase === "ready" && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {templates.data.map((template) => (
              <ScenarioCard key={template.id} template={template} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="recent-runs-heading" className="space-y-4">
        <h2 id="recent-runs-heading" className="text-lg font-semibold text-foreground">
          Recent runs
        </h2>
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
        {runs.phase === "ready" && (
          <RunsTable runs={runs.data} caption="Recent runs" />
        )}
      </section>
    </div>
  );
}
