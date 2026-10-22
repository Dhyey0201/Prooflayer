"use client";

import { ErrorPanel } from "@/components/ErrorPanel";
import { CheckOutcomePill, VerdictPill } from "@/components/StatusPill";
import { useCertificate } from "@/lib/api/useCertificate";
import type { Certificate, CertificateEntry, CheckOutcome } from "@/lib/api/types";

const CHECK_OUTCOMES: readonly string[] = ["PASS", "FAIL", "INCONCLUSIVE"];

function isCheckOutcome(value: unknown): value is CheckOutcome {
  return typeof value === "string" && CHECK_OUTCOMES.includes(value);
}

function EntryTable({ title, entries }: { title: string; entries: CertificateEntry[] }) {
  if (entries.length === 0) {
    return <p className="text-sm text-muted">No {title.toLowerCase()} recorded.</p>;
  }
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted">{title}</p>
      {entries.map((entry, index) => (
        <div key={index} className="rounded-lg border border-border bg-background p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-medium text-foreground">
              {typeof entry.requirement_id === "string"
                ? entry.requirement_id
                : typeof entry.id === "string"
                  ? entry.id
                  : `${title} ${index + 1}`}
            </span>
            {isCheckOutcome(entry.outcome) && <CheckOutcomePill outcome={entry.outcome} />}
          </div>
          <pre className="mt-2 overflow-x-auto text-xs text-foreground/80">
            {JSON.stringify(entry, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function CertificateView({ certificate }: { certificate: Certificate }) {
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

      <div>
        <p className="text-xs font-medium text-muted">Evidence manifest SHA-256</p>
        <p className="break-all font-mono text-xs text-foreground">
          {certificate.evidence_manifest_sha256}
        </p>
      </div>

      {certificate.limitations && certificate.limitations.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted">Limitations</p>
          <ul className="mt-1 list-inside list-disc text-xs text-foreground/80">
            {certificate.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      )}

      <EntryTable title="Claims" entries={certificate.claims} />
      <EntryTable title="Checks" entries={certificate.checks ?? []} />
    </div>
  );
}

export function CertificateExplorer({ runId }: { runId: string }) {
  const status = useCertificate(runId);

  if (status.phase === "loading") {
    return (
      <p role="status" className="text-sm text-muted">
        Checking for a certificate&hellip;
      </p>
    );
  }

  if (status.phase === "not_ready") {
    return (
      <div className="rounded-xl border border-dashed border-border p-6 text-center">
        <p className="text-sm font-medium text-foreground">No certificate yet</p>
        <p className="mt-1 text-sm text-muted">
          The independent verifier isn&apos;t built yet (Commit 09), so this run has no issued
          certificate. Every run currently concludes INCONCLUSIVE rather than VERIFIED or FAILED.
        </p>
        <button
          type="button"
          onClick={status.refresh}
          className="mt-3 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface"
        >
          Check again
        </button>
      </div>
    );
  }

  if (status.phase === "error") {
    return (
      <ErrorPanel message={status.message} requestId={status.requestId} onRetry={status.refresh} />
    );
  }

  return <CertificateView certificate={status.data} />;
}
