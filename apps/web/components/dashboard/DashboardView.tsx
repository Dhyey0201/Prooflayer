"use client";

import { ErrorPanel } from "@/components/ErrorPanel";
import { DashboardHero } from "@/components/dashboard/DashboardHero";
import { RunsTable } from "@/components/dashboard/RunsTable";
import { ScenarioCard } from "@/components/dashboard/ScenarioCard";
import { SystemStatusPanel } from "@/components/dashboard/SystemStatusPanel";
import { useRuns } from "@/lib/api/useRuns";
import { useTemplates } from "@/lib/api/useTemplates";

export function DashboardView() {
  const templates = useTemplates();
  const runs = useRuns(5);

  return (
    <div className="space-y-12">
      <DashboardHero />

      <section aria-labelledby="scenarios-heading" className="scroll-mt-6 space-y-4">
        <div>
          <h2 id="scenarios-heading" className="text-xl font-semibold text-foreground">
            Scenarios
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Three pre-seeded fixtures the demo replays end to end. Launching a run queues it; the
            backend worker runs the agent in a sandbox, then the independent verifier grades it
            against the pinned checks. Open a run to see its claim, evidence and certificate.
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
        <h2 id="recent-runs-heading" className="text-xl font-semibold text-foreground">
          Recent runs
        </h2>
        {runs.phase === "loading" && (
          <p role="status" className="text-sm text-muted">
            Loading runs&hellip;
          </p>
        )}
        {runs.phase === "error" && (
          <ErrorPanel message={runs.message} requestId={runs.requestId} onRetry={runs.refresh} />
        )}
        {runs.phase === "ready" && <RunsTable runs={runs.data} caption="Recent runs" />}
      </section>

      <SystemStatusPanel />
    </div>
  );
}
