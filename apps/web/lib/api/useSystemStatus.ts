"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiRequestError, getCapabilities, getHealth } from "./client";
import type { CapabilitiesResponse, HealthResponse } from "./types";

export interface SystemStatus {
  health: HealthResponse | null;
  capabilities: CapabilitiesResponse | null;
}

export type SystemStatusState =
  | { phase: "loading" }
  | { phase: "error"; message: string; requestId: string | null }
  | { phase: "ready"; data: SystemStatus };

/**
 * Fetches `/health` and `/capabilities` from the real backend on mount.
 * Never reads fixture data and never falls back to a fabricated "ok" state
 * on failure — a failed fetch stays an explicit error.
 */
export function useSystemStatus(): SystemStatusState & { refresh: () => void } {
  const [state, setState] = useState<SystemStatusState>({ phase: "loading" });
  const [attempt, setAttempt] = useState(0);

  const refresh = useCallback(() => {
    setState({ phase: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [health, capabilities] = await Promise.all([
          getHealth(),
          getCapabilities(),
        ]);
        if (!cancelled) {
          setState({ phase: "ready", data: { health, capabilities } });
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiRequestError) {
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
  }, [attempt]);

  return { ...state, refresh };
}
