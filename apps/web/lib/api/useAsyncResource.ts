"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiRequestError } from "./client";

export type AsyncResourceState<T> =
  | { phase: "loading" }
  | { phase: "error"; message: string; requestId: string | null }
  | { phase: "ready"; data: T };

/**
 * Fetches `fetcher()` on mount and exposes an explicit loading/error/ready
 * state — never a fabricated value on failure. `refresh` re-fetches and
 * flashes `loading` again; an optional `pollMs` re-fetches silently in the
 * background (no loading flash) so polling never hides a previously
 * rendered, still-valid result.
 */
export function useAsyncResource<T>(
  fetcher: () => Promise<T>,
  options?: { pollMs?: number },
): AsyncResourceState<T> & { refresh: () => void } {
  const [state, setState] = useState<AsyncResourceState<T>>({ phase: "loading" });
  const [attempt, setAttempt] = useState(0);

  const refresh = useCallback(() => {
    setState({ phase: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetcher();
        if (!cancelled) setState({ phase: "ready", data });
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
    const timer = options?.pollMs ? setInterval(() => void load(), options.pollMs) : undefined;
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
    // `fetcher`/`options` are expected to be stable per call site; `attempt`
    // is the only intended re-run trigger for `refresh()`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  return { ...state, refresh };
}
