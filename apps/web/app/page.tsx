import { RunsTable } from "@/components/dashboard/RunsTable";
import { ScenarioCard } from "@/components/dashboard/ScenarioCard";
import { SystemStatusPanel } from "@/components/dashboard/SystemStatusPanel";
import { SAMPLE_RUNS } from "@/lib/fixtures/runs";
import { SAMPLE_SCENARIO_TEMPLATES } from "@/lib/fixtures/templates";

export default function DashboardPage() {
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
            Three pre-seeded fixtures the demo replays end to end.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SAMPLE_SCENARIO_TEMPLATES.map((template) => (
            <ScenarioCard key={template.id} template={template} />
          ))}
        </div>
      </section>

      <section aria-labelledby="recent-runs-heading" className="space-y-4">
        <h2 id="recent-runs-heading" className="text-lg font-semibold text-foreground">
          Recent runs
        </h2>
        <RunsTable runs={SAMPLE_RUNS} isSample caption="Recent runs" />
      </section>
    </div>
  );
}
