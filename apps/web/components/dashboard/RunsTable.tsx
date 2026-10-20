import Link from "next/link";

import { RunStatusPill, VerdictPill } from "@/components/StatusPill";
import type { Run } from "@/lib/api/types";

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function RunsTable({ runs, caption }: { runs: Run[]; caption?: string }) {
  if (runs.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">
        No runs yet. Launch a scenario from the dashboard to start one.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface/60">
      <div className="border-b border-border p-4">
        <p className="text-sm font-semibold text-foreground">{caption ?? "Runs"}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{caption ?? "Runs"}</caption>
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
              <tr key={run.id} className="hover:bg-background/40">
                <td className="px-4 py-3">
                  <Link
                    href={`/runs/${run.id}`}
                    className="font-mono text-xs text-accent hover:underline"
                  >
                    {run.template_id}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <RunStatusPill status={run.status} />
                </td>
                <td className="px-4 py-3">
                  <VerdictPill verdict={run.verdict} />
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
