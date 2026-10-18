import { RunStatusPill, VerdictPill } from "@/components/StatusPill";
import { SampleDataBadge } from "@/components/SampleDataBadge";
import type { Run } from "@/lib/api/types";

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function RunsTable({
  runs,
  isSample,
  caption,
}: {
  runs: Run[];
  isSample: boolean;
  caption?: string;
}) {
  if (runs.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">
        No runs yet. Launching runs ships in Commit 03/04.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface/60">
      <div className="flex items-center justify-between gap-3 border-b border-border p-4">
        <p className="text-sm font-semibold text-foreground">{caption ?? "Runs"}</p>
        {isSample && <SampleDataBadge />}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">
            {caption ?? "Runs"}
            {isSample ? ", sample data, not a live backend result" : ""}
          </caption>
          <thead>
            <tr className="text-xs uppercase tracking-wide text-muted">
              <th scope="col" className="px-4 py-2">
                Scenario
              </th>
              <th scope="col" className="px-4 py-2">
                Status
              </th>
              <th scope="col" className="px-4 py-2">
                Verdict
              </th>
              <th scope="col" className="px-4 py-2">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {runs.map((run) => (
              <tr key={run.id}>
                <td className="px-4 py-3 font-mono text-xs text-foreground">
                  {run.template_id}
                </td>
                <td className="px-4 py-3">
                  <RunStatusPill status={run.status} />
                </td>
                <td className="px-4 py-3">
                  <VerdictPill verdict={run.verdict ?? null} />
                </td>
                <td className="px-4 py-3 text-xs text-muted">
                  {formatTimestamp(run.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
