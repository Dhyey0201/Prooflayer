"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiRequestError, cancelRun, getRun, getRunEvents } from "./client";
import { ACTIVE_RUN_STATUSES } from "./types";
import type { Event, Run } from "./types";

export type RunDetailState =
  | { phase: "loading" }
  | { phase: "error"; message: string; requestId: string | null }
  | { phase: "ready"; run: Run; events: Event[] };

export type CancelState = "idle" | "pending" | { error: string };

const POLL_MS = 3000;

/**
 * Polls `GET /runs/{id}` and `GET /runs/{id}/events` (incrementally, via
 * `after_seq`) until the run reaches a terminal status, then stops. Pass a
 * stable `runId` for the lifetime of the calling component — mount a fresh
 * instance (e.g. `key={runId}`) if the id can change.
 */
export function useRunDetail(runId: string) {
  const [state, setState] = useState<RunDetailState>({ phase: "loading" });
  const [cancelState, setCancelState] = useState<CancelState>("idle");

  useEffect(() => {
    let cancelled = false;
    let lastSeq = 0;
    let timer: ReturnType<typeof setInterval> | undefined;

    async function poll() {
      try {
        const run = await getRun(runId);
        const newEvents = await getRunEvents(runId, lastSeq);
        if (cancelled) return;
        if (newEvents.length > 0) {
          lastSeq = newEvents[newEvents.length - 1].seq;
        }
        setState((prev) => ({
          phase: "ready",
          run,
          events: prev.phase === "ready" ? [...prev.events, ...newEvents] : newEvents,
        }));
        if (!ACTIVE_RUN_STATUSES.includes(run.status) && timer) {
          clearInterval(timer);
          timer = undefined;
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

    void poll();
    timer = setInterval(() => void poll(), POLL_MS);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [runId]);

  const cancel = useCallback(async () => {
    setCancelState("pending");
    try {
      const run = await cancelRun(runId);
      setCancelState("idle");
      setState((prev) => (prev.phase === "ready" ? { ...prev, run } : prev));
    } catch (err) {
      setCancelState({
        error: err instanceof ApiRequestError ? err.message : "Could not cancel the run.",
      });
    }
  }, [runId]);

  return { ...state, cancel, cancelState };
}
