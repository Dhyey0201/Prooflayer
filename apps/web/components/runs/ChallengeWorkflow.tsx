"use client";

import { ErrorPanel } from "@/components/ErrorPanel";
import { CheckOutcomePill } from "@/components/StatusPill";
import { useChallenges } from "@/lib/api/useChallenges";
import type { CertificateState } from "@/lib/api/useCertificate";
import type { Challenge, ChallengeStatus } from "@/lib/api/types";

const STATUS_LABEL: Record<ChallengeStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  rejected: "Rejected",
  error: "Error",
};

const STATUS_CLASSES: Record<ChallengeStatus, string> = {
  queued: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
  running: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
  completed: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  rejected: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  error: "bg-rose-500/15 text-rose-300 ring-rose-500/30",
};

function ChallengeStatusBadge({ status }: { status: ChallengeStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold capitalize ring-1 ring-inset ${STATUS_CLASSES[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
}

function OriginalComparison({
  challenge,
  certificate,
}: {
  challenge: Challenge;
  certificate: CertificateState;
}) {
  if (certificate.phase !== "ready" || !challenge.requirement_id) return null;
  const original = certificate.data.checks.find(
    (check) => check.requirement_id === challenge.requirement_id,
  );
  if (!original || !challenge.outcome) return null;
  const agree = original.outcome === challenge.outcome;
  return (
    <p className="mt-2 text-xs text-muted">
      Original certificate check for <code>{challenge.requirement_id}</code>:{" "}
      <span className="font-mono text-foreground">{original.outcome}</span> &middot; this
      challenge: <span className="font-mono text-foreground">{challenge.outcome}</span> &mdash;{" "}
      <span className={agree ? "text-emerald-300" : "text-rose-300"}>
        {agree ? "agree" : "disagree"}
      </span>
    </p>
  );
}

function ChallengeCard({
  challenge,
  certificate,
}: {
  challenge: Challenge;
  certificate: CertificateState;
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <code className="text-xs text-foreground">{challenge.requirement_id ?? "—"}</code>
        <div className="flex items-center gap-2">
          {challenge.outcome && <CheckOutcomePill outcome={challenge.outcome} />}
          <ChallengeStatusBadge status={challenge.status} />
        </div>
      </div>

      {challenge.validated === false && (
        <p className="mt-2 text-xs text-amber-300">
          Rejected by static validation — never executed{challenge.reason ? ` (${challenge.reason})` : ""}.
        </p>
      )}

      {challenge.test_source && (
        <div className="mt-2">
          <p className="text-xs font-medium text-muted">
            Proposed test (untrusted model output — shown as code, never executed as HTML)
          </p>
          <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-surface/60 p-2 text-xs text-foreground/90">
            <code>{challenge.test_source}</code>
          </pre>
        </div>
      )}

      <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <div>
          <dt className="text-muted">Exit code</dt>
          <dd className="font-mono text-foreground">{challenge.exit_code ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-muted">Duration</dt>
          <dd className="font-mono text-foreground">
            {challenge.duration_ms === null ? "—" : `${challenge.duration_ms} ms`}
          </dd>
        </div>
        <div className="truncate">
          <dt className="text-muted">Output hash</dt>
          <dd
            className="truncate font-mono text-foreground"
            title={challenge.output_sha256 ?? ""}
          >
            {challenge.output_sha256 ? `${challenge.output_sha256.slice(0, 12)}…` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Requested</dt>
          <dd className="font-mono text-foreground">{formatTimestamp(challenge.created_at)}</dd>
        </div>
      </dl>

      <OriginalComparison challenge={challenge} certificate={certificate} />
    </div>
  );
}

export function ChallengeWorkflow({
  runId,
  canChallenge,
  certificate,
}: {
  runId: string;
  canChallenge: boolean;
  certificate: CertificateState;
}) {
  const { request, requestState, ...status } = useChallenges(runId);
  const hasActiveChallenge =
    status.phase === "ready" && status.data.some((c) => c.status === "queued" || c.status === "running");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface/60 p-4">
        <div>
          <p className="text-sm font-medium text-foreground">Proof challenge</p>
          <p className="mt-1 text-xs text-muted">
            Asks the model for one additional pytest test, validates it statically, then runs it
            only in the independent verifier against this run&apos;s recorded workspace. Never
            changes the certificate above.
          </p>
        </div>
        <div>
          <button
            type="button"
            onClick={() => void request()}
            disabled={!canChallenge || hasActiveChallenge || requestState === "pending"}
            className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {requestState === "pending" ? "Requesting…" : "Request challenge"}
          </button>
          {!canChallenge && (
            <p className="mt-1 text-xs text-muted">Available once this run is certified.</p>
          )}
          {canChallenge && hasActiveChallenge && (
            <p className="mt-1 text-xs text-muted">A challenge is already in progress.</p>
          )}
          {typeof requestState === "object" && (
            <p role="alert" className="mt-1 text-xs text-rose-300">
              {requestState.error}
            </p>
          )}
        </div>
      </div>

      {status.phase === "loading" && (
        <p role="status" className="text-sm text-muted">
          Loading challenges&hellip;
        </p>
      )}
      {status.phase === "error" && (
        <ErrorPanel message={status.message} requestId={status.requestId} />
      )}
      {status.phase === "ready" && status.data.length === 0 && (
        <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted">
          No challenges requested yet.
        </div>
      )}
      {status.phase === "ready" && status.data.length > 0 && (
        <div className="space-y-2">
          {status.data
            .slice()
            .reverse()
            .map((challenge) => (
              <ChallengeCard key={challenge.id} challenge={challenge} certificate={certificate} />
            ))}
        </div>
      )}
    </div>
  );
}
