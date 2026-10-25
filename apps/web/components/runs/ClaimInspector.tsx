import { CheckOutcomePill } from "@/components/StatusPill";
import { PolicyPreview } from "@/components/dashboard/PolicyPreview";
import { ClaimVsEvidence } from "@/components/runs/ClaimVsEvidence";
import type { CertificateState } from "@/lib/api/useCertificate";
import type { Event, Run, Template } from "@/lib/api/types";

const CLAIM_REQUIREMENT = "pytest-full-suite";

function lastEventOfType(events: Event[], type: Event["event_type"]): Event | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i].event_type === type) return events[i];
  }
  return null;
}

function PendingPill() {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-500/15 px-2.5 py-1 text-xs font-semibold text-slate-300 ring-1 ring-inset ring-slate-500/30">
      PENDING — verification not complete
    </span>
  );
}

function MeasurementChips({ measurements }: { measurements: Record<string, unknown> }) {
  const entries = Object.entries(measurements);
  if (entries.length === 0) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {entries.map(([key, value]) => (
        <code
          key={key}
          className="rounded bg-background px-1.5 py-0.5 text-xs text-muted ring-1 ring-inset ring-border"
        >
          {key}={String(value)}
        </code>
      ))}
    </div>
  );
}

function ClaimFallbackPanel({ run, events }: { run: Run; events: Event[] }) {
  const claimed = lastEventOfType(events, "agent.claimed");

  if (!run.agent_claim && !claimed) {
    return (
      <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted">
        No agent claim yet.
      </div>
    );
  }

  const testsPassed = claimed ? claimed.safe_payload.tests_passed : null;

  return (
    <div className="rounded-xl border border-border bg-surface/60 p-4">
      <p className="text-xs font-medium text-muted">Agent claim — untrusted</p>
      <p className="mt-1 text-sm text-foreground">
        {run.agent_claim ?? <span className="text-muted">(claim text unavailable)</span>}
      </p>
      {claimed && (
        <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
          <div>
            <dt className="text-muted">Self-reported tests</dt>
            <dd className="font-mono text-foreground">
              {testsPassed === null ? "unknown" : testsPassed ? "passed" : "failed"}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Claim length</dt>
            <dd className="font-mono text-foreground">
              {String(claimed.safe_payload.claim_chars)} chars
            </dd>
          </div>
          <div>
            <dt className="text-muted">Claim hash</dt>
            <dd
              className="truncate font-mono text-foreground"
              title={String(claimed.safe_payload.claim_sha256)}
            >
              {String(claimed.safe_payload.claim_sha256).slice(0, 16)}&hellip;
            </dd>
          </div>
        </dl>
      )}
      <p className="mt-3 text-xs text-muted">
        Verification hasn&apos;t finished yet, so this can&apos;t be compared against a
        measurement.
      </p>
    </div>
  );
}

function EvidenceStatusPanel({
  template,
  certificate,
}: {
  template: Template;
  certificate: CertificateState;
}) {
  const checks = certificate.phase === "ready" ? certificate.data.checks : [];

  return (
    <div className="rounded-xl border border-border bg-surface/60 p-4">
      <p className="text-xs font-medium text-muted">Evidence status per required check</p>
      <ul className="mt-2 space-y-2">
        {template.required_checks.map((requirementId) => {
          const check = checks.find((c) => c.requirement_id === requirementId) ?? null;
          return (
            <li
              key={requirementId}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2"
            >
              <div>
                <code className="text-xs text-foreground">{requirementId}</code>
                {check && <MeasurementChips measurements={check.measurements} />}
              </div>
              <div className="flex items-center gap-2">
                {check?.reason && <span className="text-xs text-muted">{check.reason}</span>}
                {check ? <CheckOutcomePill outcome={check.outcome} /> : <PendingPill />}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs text-muted">
        Outcomes come only from the independent verifier&apos;s measurements — never from the
        agent&apos;s own account.
      </p>
    </div>
  );
}

export function ClaimInspector({
  run,
  events,
  template,
  certificate,
}: {
  run: Run;
  events: Event[];
  template: Template | null;
  certificate: CertificateState;
}) {
  const claim =
    certificate.phase === "ready"
      ? certificate.data.claims.find((c) => c.requirement_id === CLAIM_REQUIREMENT) ??
        certificate.data.claims[0] ??
        null
      : null;
  const matchingCheck =
    certificate.phase === "ready" && claim
      ? certificate.data.checks.find((c) => c.requirement_id === claim.requirement_id) ?? null
      : null;

  return (
    <div className="space-y-4">
      {template ? (
        <div>
          <p className="mb-2 text-xs font-medium text-muted">Requirements</p>
          <div className="rounded-xl border border-border bg-surface/60 p-4">
            <PolicyPreview template={template} />
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted">
          Requirements unavailable — could not load this run&apos;s template.
        </div>
      )}

      {certificate.phase === "ready" ? (
        <ClaimVsEvidence claim={claim} check={matchingCheck} />
      ) : (
        <ClaimFallbackPanel run={run} events={events} />
      )}

      {template && <EvidenceStatusPanel template={template} certificate={certificate} />}
    </div>
  );
}
