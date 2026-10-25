"use client";

import { ErrorPanel } from "@/components/ErrorPanel";
import { RunStatusPill, VerdictPill } from "@/components/StatusPill";
import { CertificateExplorer } from "@/components/runs/CertificateExplorer";
import { ChallengeWorkflow } from "@/components/runs/ChallengeWorkflow";
import { ClaimInspector } from "@/components/runs/ClaimInspector";
import { EventTrace } from "@/components/runs/EventTrace";
import { Tabs } from "@/components/runs/Tabs";
import { ACTIVE_RUN_STATUSES } from "@/lib/api/types";
import { useCertificate } from "@/lib/api/useCertificate";
import { useRunDetail } from "@/lib/api/useRunDetail";
import { useTemplates } from "@/lib/api/useTemplates";

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
}

export function RunDetailView({ runId }: { runId: string }) {
  const { cancel, cancelState, ...status } = useRunDetail(runId);
  const templates = useTemplates();
  // Poll for a certificate while the run has no verdict yet; stop once it
  // does, or once it's terminal with no verdict coming (canceled/error).
  const shouldPollCertificate =
    status.phase === "ready" &&
    status.run.verdict === null &&
    status.run.status !== "canceled" &&
    status.run.status !== "error";
  const certificate = useCertificate(runId, shouldPollCertificate);

  if (status.phase === "loading") {
    return (
      <p role="status" className="text-sm text-muted">
        Loading run&hellip;
      </p>
    );
  }

  if (status.phase === "error") {
    return <ErrorPanel message={status.message} requestId={status.requestId} />;
  }

  const { run, events } = status;
  const isActive = ACTIVE_RUN_STATUSES.includes(run.status);
  const template =
    templates.phase === "ready"
      ? templates.data.find((candidate) => candidate.id === run.template_id) ?? null
      : null;

  return (
    <div className="space-y-6">
      <header className="rounded-xl border border-border bg-surface/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs text-muted">{run.id}</p>
            <h1 className="mt-1 text-xl font-semibold text-foreground">{run.template_id}</h1>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-sky-500/15 px-2.5 py-1 text-xs font-semibold text-sky-300 ring-1 ring-inset ring-sky-500/30">
              {run.mode} mode
            </span>
            <RunStatusPill status={run.status} />
            <VerdictPill verdict={run.verdict} />
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
          <div>
            <dt className="text-muted">Created</dt>
            <dd className="text-foreground">{formatTimestamp(run.created_at)}</dd>
          </div>
          <div>
            <dt className="text-muted">Updated</dt>
            <dd className="text-foreground">{formatTimestamp(run.updated_at)}</dd>
          </div>
          <div className="col-span-2 sm:col-span-2">
            <dt className="text-muted">Agent claim</dt>
            <dd className="text-foreground">
              {run.agent_claim ?? <span className="text-muted">none yet</span>}
            </dd>
          </div>
        </dl>

        {isActive && (
          <p className="mt-4 rounded-lg border border-sky-400/30 bg-sky-400/10 px-3 py-2 text-xs text-sky-200">
            In progress — the backend worker runs the agent, then the independent verifier grades
            it against the pinned checks. The Certificate tab fills in once that finishes.
          </p>
        )}

        {isActive && (
          <div className="mt-4">
            <button
              type="button"
              onClick={cancel}
              disabled={cancelState === "pending"}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface disabled:cursor-wait disabled:opacity-60"
            >
              {cancelState === "pending" ? "Cancelling…" : "Cancel run"}
            </button>
            {typeof cancelState === "object" && (
              <p role="alert" className="mt-2 text-xs text-rose-300">
                {cancelState.error}
              </p>
            )}
          </div>
        )}
      </header>

      <Tabs
        tabs={[
          {
            id: "trace",
            label: "Event trace",
            content: <EventTrace events={events} />,
          },
          {
            id: "claim",
            label: "Claim inspector",
            content: (
              <ClaimInspector
                run={run}
                events={events}
                template={template}
                certificate={certificate}
              />
            ),
          },
          {
            id: "certificate",
            label: "Certificate",
            content: <CertificateExplorer certificate={certificate} />,
          },
          {
            id: "challenges",
            label: "Challenges",
            content: (
              <ChallengeWorkflow
                runId={run.id}
                canChallenge={run.verdict !== null}
                certificate={certificate}
              />
            ),
          },
        ]}
      />
    </div>
  );
}
