import { CheckOutcomePill, ClaimStatusPill } from "@/components/StatusPill";
import type { CertificateCheck, CertificateClaim } from "@/lib/api/types";

const HEADLINE: Record<CertificateClaim["status"], string> = {
  SUPPORTED: "The agent's claim matches what the verifier measured.",
  CONTRADICTED: "The agent's claim is contradicted by what the verifier measured.",
  UNVERIFIED: "The agent's claim could not be checked against a measurement.",
};

const BANNER_CLASSES: Record<CertificateClaim["status"], string> = {
  SUPPORTED: "border-emerald-500/30 bg-emerald-500/10",
  CONTRADICTED: "border-rose-500/30 bg-rose-500/10",
  UNVERIFIED: "border-amber-500/30 bg-amber-500/10",
};

function agentSaid(claim: CertificateClaim): string {
  if (claim.asserts_tests_passed === null) return "made a claim of unknown shape";
  return claim.asserts_tests_passed ? "tests passed" : "tests failed";
}

/**
 * "Before" (what the agent claimed) vs "after" (what the independent
 * verifier actually measured) — the comparison is `claim.status`, computed
 * server-side from the measured check, never re-derived here.
 */
export function ClaimVsEvidence({
  claim,
  check,
}: {
  claim: CertificateClaim | null;
  check: CertificateCheck | null;
}) {
  if (!claim) {
    return (
      <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted">
        No agent claim was recorded for this run.
      </div>
    );
  }

  return (
    <div className={`rounded-xl border p-4 ${BANNER_CLASSES[claim.status]}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-foreground">{HEADLINE[claim.status]}</p>
        <ClaimStatusPill status={claim.status} />
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-medium text-muted">Agent said (untrusted)</p>
          <p className="mt-1 text-sm text-foreground">The {agentSaid(claim)}.</p>
          <p className="mt-2 font-mono text-xs text-muted">
            sha256:{claim.statement_sha256.slice(0, 16)}&hellip; &middot; {claim.statement_chars}{" "}
            chars
          </p>
        </div>
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-medium text-muted">Verifier measured</p>
          {check ? (
            <>
              <div className="mt-1 flex items-center gap-2">
                <code className="text-xs text-foreground">{check.requirement_id}</code>
                <CheckOutcomePill outcome={check.outcome} />
              </div>
              {check.reason && (
                <p className="mt-1 font-mono text-xs text-muted">{check.reason}</p>
              )}
            </>
          ) : (
            <p className="mt-1 text-sm text-muted">No matching check was recorded.</p>
          )}
        </div>
      </div>
    </div>
  );
}
