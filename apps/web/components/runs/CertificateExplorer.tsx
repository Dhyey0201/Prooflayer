import { ErrorPanel } from "@/components/ErrorPanel";
import { CheckOutcomePill, ClaimStatusPill, VerdictPill } from "@/components/StatusPill";
import type { CertificateState } from "@/lib/api/useCertificate";
import type { Certificate } from "@/lib/api/types";

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function Hash({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="break-all font-mono text-xs text-foreground">{value}</p>
    </div>
  );
}

function ChecksTable({ checks }: { checks: Certificate["checks"] }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted">Independent checks</p>
      {checks.map((check) => (
        <div
          key={check.requirement_id}
          className="rounded-lg border border-border bg-background p-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <code className="text-xs font-medium text-foreground">{check.requirement_id}</code>
            <CheckOutcomePill outcome={check.outcome} />
          </div>
          <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div>
              <dt className="text-muted">Reason</dt>
              <dd className="font-mono text-foreground">{check.reason ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted">Exit code</dt>
              <dd className="font-mono text-foreground">{check.exit_code ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted">Duration</dt>
              <dd className="font-mono text-foreground">
                {check.duration_ms === null ? "—" : `${check.duration_ms} ms`}
              </dd>
            </div>
            <div className="truncate">
              <dt className="text-muted">Output hash</dt>
              <dd className="truncate font-mono text-foreground" title={check.output_sha256 ?? ""}>
                {check.output_sha256 ? `${check.output_sha256.slice(0, 12)}…` : "—"}
              </dd>
            </div>
          </dl>
          {Object.keys(check.measurements).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {Object.entries(check.measurements).map(([key, value]) => (
                <code
                  key={key}
                  className="rounded bg-surface/60 px-1.5 py-0.5 text-xs text-muted ring-1 ring-inset ring-border"
                >
                  {key}={String(value)}
                </code>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ClaimsTable({ claims }: { claims: Certificate["claims"] }) {
  if (claims.length === 0) {
    return <p className="text-sm text-muted">No agent claim recorded.</p>;
  }
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted">Claims</p>
      {claims.map((claim) => (
        <div key={claim.claim_id} className="rounded-lg border border-border bg-background p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <code className="text-xs text-foreground">{claim.requirement_id}</code>
            <ClaimStatusPill status={claim.status} />
          </div>
          <p className="mt-1 font-mono text-xs text-muted">
            untrusted &middot; sha256:{claim.statement_sha256.slice(0, 16)}&hellip; &middot;{" "}
            {claim.statement_chars} chars
          </p>
        </div>
      ))}
    </div>
  );
}

function ManifestPanel({ manifest }: { manifest: Certificate["manifest"] }) {
  return (
    <div className="space-y-2 rounded-lg border border-border bg-background p-3 text-xs">
      <p className="font-medium text-muted">Manifest</p>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <div>
          <dt className="text-muted">Events through seq</dt>
          <dd className="font-mono text-foreground">{manifest.events_through_seq}</dd>
        </div>
        <div>
          <dt className="text-muted">Chain valid</dt>
          <dd className="font-mono text-foreground">{String(manifest.event_chain_valid)}</dd>
        </div>
        <div>
          <dt className="text-muted">Issued</dt>
          <dd className="font-mono text-foreground">
            {new Date(manifest.issued_at).toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Sandbox driver / enforced</dt>
          <dd className="font-mono text-foreground">
            {manifest.agent.sandbox_driver ?? "—"} / {String(manifest.agent.sandbox_enforced)}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Verifier</dt>
          <dd className="font-mono text-foreground">
            {manifest.verifier
              ? `${manifest.verifier.driver} (${manifest.verifier.isolation}, network: ${manifest.verifier.network})`
              : "unavailable"}
          </dd>
        </div>
        {manifest.verifier && (
          <div className="truncate">
            <dt className="text-muted">Verifier image</dt>
            <dd className="truncate font-mono text-foreground" title={manifest.verifier.image_id}>
              {manifest.verifier.image_id.slice(0, 16)}&hellip;
            </dd>
          </div>
        )}
      </dl>
      {manifest.artifacts.length > 0 && (
        <div>
          <p className="text-muted">Artifacts</p>
          <ul className="mt-1 space-y-1">
            {manifest.artifacts.map((artifact) => (
              <li key={`${artifact.type}-${artifact.sha256}`} className="truncate font-mono">
                {artifact.type}: {artifact.sha256.slice(0, 16)}&hellip;
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function CertificateView({
  certificate,
  certificateSha256,
}: {
  certificate: Certificate;
  certificateSha256: string | null;
}) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface/60 p-4">
        <div className="flex items-center gap-3">
          <VerdictPill verdict={certificate.verdict} />
          <span className="text-xs text-muted">
            Certificate schema {certificate.schema_version}
          </span>
        </div>
        <button
          type="button"
          onClick={() => downloadJson(`${certificate.run_id}.certificate.json`, certificate)}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface"
        >
          Download JSON
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Hash label="Evidence manifest SHA-256" value={certificate.evidence_manifest_sha256} />
        {certificateSha256 && <Hash label="Certificate SHA-256 (this response)" value={certificateSha256} />}
      </div>

      {certificate.limitations.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted">Limitations</p>
          <ul className="mt-1 list-inside list-disc text-xs text-foreground/80">
            {certificate.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      )}

      <ClaimsTable claims={certificate.claims} />
      <ChecksTable checks={certificate.checks} />
      <ManifestPanel manifest={certificate.manifest} />
    </div>
  );
}

export function CertificateExplorer({ certificate }: { certificate: CertificateState }) {
  if (certificate.phase === "loading") {
    return (
      <p role="status" className="text-sm text-muted">
        Checking for a certificate&hellip;
      </p>
    );
  }

  if (certificate.phase === "not_ready") {
    return (
      <div className="rounded-xl border border-dashed border-border p-6 text-center">
        <p className="text-sm font-medium text-foreground">No certificate yet</p>
        <p className="mt-1 text-sm text-muted">
          The independent verifier hasn&apos;t graded this run yet.
        </p>
      </div>
    );
  }

  if (certificate.phase === "error") {
    return <ErrorPanel message={certificate.message} requestId={certificate.requestId} />;
  }

  return (
    <CertificateView
      certificate={certificate.data}
      certificateSha256={certificate.certificateSha256}
    />
  );
}
