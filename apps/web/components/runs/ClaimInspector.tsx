import { PolicyPreview } from "@/components/dashboard/PolicyPreview";
import type { Event, Run, Template } from "@/lib/api/types";

function lastEventOfType(events: Event[], type: Event["event_type"]): Event | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i].event_type === type) return events[i];
  }
  return null;
}

function countEventsOfType(events: Event[], type: Event["event_type"]): number {
  return events.filter((event) => event.event_type === type).length;
}

function InconclusivePill({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-semibold text-amber-300 ring-1 ring-inset ring-amber-500/30">
      {label}
    </span>
  );
}

function ClaimPanel({ run, events }: { run: Run; events: Event[] }) {
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
      <p className="text-xs font-medium text-muted">Agent claim &mdash; untrusted</p>
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
        This is what the agent says happened &mdash; never evidence that it did.
      </p>
    </div>
  );
}

function EvidenceStatusPanel({ template, events }: { template: Template; events: Event[] }) {
  const deniedAttempts = countEventsOfType(events, "policy.denied");
  const sandbox = lastEventOfType(events, "sandbox.provisioned");
  const enforced = sandbox ? Boolean(sandbox.safe_payload.enforced) : null;

  return (
    <div className="rounded-xl border border-border bg-surface/60 p-4">
      <p className="text-xs font-medium text-muted">Evidence status per required check</p>
      <ul className="mt-2 space-y-2">
        {template.required_checks.map((check) => (
          <li
            key={check}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2"
          >
            <code className="text-xs text-foreground">{check}</code>
            <div className="flex items-center gap-2">
              {check === "no-forbidden-access-attempts" && (
                <span className="text-xs text-muted">
                  {deniedAttempts} forbidden attempt{deniedAttempts === 1 ? "" : "s"} observed, all
                  denied
                </span>
              )}
              <InconclusivePill label="INCONCLUSIVE — not independently measured" />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">
        No check here is promoted to PASS or FAIL until the independent verifier exists (Commit
        09). Sandbox enforcement:{" "}
        <span className="font-mono text-foreground">
          {enforced === null ? "unknown" : enforced ? "enforced" : "not enforced (mock mode)"}
        </span>
        .
      </p>
    </div>
  );
}

export function ClaimInspector({
  run,
  events,
  template,
}: {
  run: Run;
  events: Event[];
  template: Template | null;
}) {
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
          Requirements unavailable &mdash; could not load this run&apos;s template.
        </div>
      )}
      <ClaimPanel run={run} events={events} />
      {template && <EvidenceStatusPanel template={template} events={events} />}
    </div>
  );
}
