import { VerdictPill } from "@/components/StatusPill";
import type { ScenarioTemplate } from "@/lib/fixtures/templates";

export function ScenarioCard({ template }: { template: ScenarioTemplate }) {
  return (
    <article className="flex h-full flex-col justify-between rounded-xl border border-border bg-surface/60 p-5 transition-colors hover:border-accent/40">
      <div>
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-base font-semibold text-foreground">{template.name}</h3>
          <VerdictPill verdict={template.expectedVerdict} />
        </div>
        <p className="mt-2 text-sm text-muted">{template.summary}</p>
        <p className="mt-3 text-sm leading-relaxed text-foreground/80">
          {template.description}
        </p>
      </div>
      <button
        type="button"
        disabled
        aria-disabled="true"
        title="Run creation lands in Commit 03/04"
        className="mt-4 w-full cursor-not-allowed rounded-lg border border-border px-3 py-2 text-sm font-medium text-muted"
      >
        Launch run (coming soon)
      </button>
    </article>
  );
}
