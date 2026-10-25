"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiRequestError, listChallenges, requestChallenge } from "./client";
import { ACTIVE_CHALLENGE_STATUSES } from "./types";
import type { Challenge } from "./types";

export type ChallengesState =
  | { phase: "loading" }
  | { phase: "error"; message: string; requestId: string | null }
  | { phase: "ready"; data: Challenge[] };

export type RequestState = "idle" | "pending" | { error: string };

const POLL_MS = 2000;

/** Lists a run's proof challenges, polling only while one is queued/running. */
export function useChallenges(runId: string) {
  const [state, setState] = useState<ChallengesState>({ phase: "loading" });
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    async function load() {
      try {
        const data = await listChallenges(runId);
        if (cancelled) return;
        setState({ phase: "ready", data });
        const stillActive = data.some((c) => ACTIVE_CHALLENGE_STATUSES.includes(c.status));
        if (!stillActive && timer) {
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

    void load();
    timer = setInterval(() => void load(), POLL_MS);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [runId, attempt]);

  const request = useCallback(async () => {
    setRequestState("pending");
    try {
      await requestChallenge(runId);
      setRequestState("idle");
      setAttempt((n) => n + 1);
    } catch (err) {
      setRequestState({
        error: err instanceof ApiRequestError ? err.message : "Could not start the challenge.",
      });
    }
  }, [runId]);

  return { ...state, request, requestState };
}
