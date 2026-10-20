"use client";

import { listRuns } from "./client";
import { useAsyncResource } from "./useAsyncResource";
import type { Run } from "./types";

const POLL_MS = 4000;

/** Fetches `GET /runs` and polls in the background so new launches show up. */
export function useRuns(limit = 50) {
  return useAsyncResource<Run[]>(() => listRuns(limit), { pollMs: POLL_MS });
}
