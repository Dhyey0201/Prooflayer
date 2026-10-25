"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiRequestError, getCertificate } from "./client";
import type { Certificate } from "./types";

export type CertificateState =
  | { phase: "loading" }
  | { phase: "not_ready" }
  | { phase: "error"; message: string; requestId: string | null }
  | { phase: "ready"; data: Certificate };

/**
 * Fetches `GET /runs/{id}/certificate`. A 404 is not an error — the contract
 * documents it as "Not ready", true whenever the independent verifier
 * (Commit 09) hasn't produced one yet — so it gets its own explicit phase
 * rather than being lumped in with a real fetch failure.
 */
export function useCertificate(runId: string) {
  const [state, setState] = useState<CertificateState>({ phase: "loading" });
  const [attempt, setAttempt] = useState(0);

  const refresh = useCallback(() => {
    setState({ phase: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await getCertificate(runId);
        if (!cancelled) setState({ phase: "ready", data });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiRequestError && err.status === 404) {
          setState({ phase: "not_ready" });
        } else if (err instanceof ApiRequestError) {
          setState({ phase: "error", message: err.message, requestId: err.requestId });
        } else {
          setState({
            phase: "error",
            message: "Unexpected error contacting the ProofLayer API.",
            requestId: null,
          });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [runId, attempt]);

  return { ...state, refresh };
}
