"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiRequestError, getCertificate } from "./client";
import type { Certificate } from "./types";

export type CertificateState =
  | { phase: "loading" }
  | { phase: "not_ready" }
  | { phase: "error"; message: string; requestId: string | null }
  | { phase: "ready"; data: Certificate; certificateSha256: string | null };

const POLL_MS = 2000;

/**
 * Fetches `GET /runs/{id}/certificate`. A 404 is not an error — the contract
 * documents it as "Not ready", true whenever the independent verifier
 * hasn't graded this run yet — so it gets its own explicit phase rather than
 * being lumped in with a real fetch failure. Pass `poll: true` while the run
 * has no verdict yet; polling stops on its own once a certificate exists or
 * the caller passes `poll: false` (e.g. once the run hits a terminal status
 * with no verdict, like `canceled`/`error`).
 */
export function useCertificate(runId: string, poll: boolean) {
  const [state, setState] = useState<CertificateState>({ phase: "loading" });
  const [attempt, setAttempt] = useState(0);

  const refresh = useCallback(() => {
    setState({ phase: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    async function load() {
      try {
        const { certificate, certificateSha256 } = await getCertificate(runId);
        if (cancelled) return;
        setState({ phase: "ready", data: certificate, certificateSha256 });
        if (timer) {
          clearInterval(timer);
          timer = undefined;
        }
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
    if (poll) {
      timer = setInterval(() => void load(), POLL_MS);
    }
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [runId, attempt, poll]);

  return { ...state, refresh };
}
