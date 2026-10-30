"use client";

import { getApiBaseUrl } from "@/lib/api/client";
import { useSystemStatus } from "@/lib/api/useSystemStatus";

const CAPABILITY_LABELS: Record<string, string> = {
  mock_mode: "Mock mode",
  nebius_configured: "Nebius configured",
  live_model_enabled: "Live model calls",
  openshell_available: "OpenShell available",
  sandbox_enforced: "Sandbox enforced",
  unenforced_live_allowed: "Live runs without enforcement",
  read_only: "Read-only replay",
  independent_verifier_available: "Independent verifier",
  tavily_enabled: "Tavily retrieval",
};

export function SystemStatusPanel() {
  const status = useSystemStatus();

  return (
    <section
      aria-labelledby="system-status-heading"
      className="rounded-xl border border-border bg-surface/60 p-5"
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 id="system-status-heading" className="text-sm font-semibold text-foreground">
            Backend status
          </h2>
          <p className="text-xs text-muted">{getApiBaseUrl()}</p>
        </div>
        {status.phase === "error" && (
          <button
            type="button"
            onClick={status.refresh}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface"
          >
            Retry
          </button>
        )}
      </div>

      {status.phase === "loading" && (
        <p role="status" className="mt-4 text-sm text-muted">
          Checking the API&hellip;
        </p>
      )}

      {status.phase === "error" && (
        <div role="alert" className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3">
          <p className="text-sm font-medium text-rose-300">Could not reach the API</p>
          <p className="mt-1 text-sm text-rose-200/80">{status.message}</p>
          {status.requestId && (
            <p className="mt-1 text-xs text-rose-200/60">Request ID: {status.requestId}</p>
          )}
        </div>
      )}

      {status.phase === "ready" && (
        <div className="mt-4 space-y-4">
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className="h-2.5 w-2.5 rounded-full bg-emerald-400"
            />
            <p className="text-sm text-foreground">
              Healthy — <span className="font-mono text-xs text-muted">{status.data.health.status}</span>
            </p>
          </div>
          <dl className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
            {Object.entries(status.data.capabilities).map(([key, value]) => (
              <div
                key={key}
                className="flex items-center justify-between rounded-lg border border-border px-3 py-2"
              >
                <dt className="text-muted">{CAPABILITY_LABELS[key] ?? key}</dt>
                <dd
                  className={`font-mono font-semibold ${value ? "text-emerald-300" : "text-muted"}`}
                >
                  {value ? "true" : "false"}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </section>
  );
}
