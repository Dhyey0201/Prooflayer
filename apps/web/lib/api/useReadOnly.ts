"use client";

import { getCapabilities } from "./client";
import { useAsyncResource } from "./useAsyncResource";

/**
 * True only once the backend itself reports `read_only` (hosted replay).
 * While loading or on error it is false, so a local backend keeps its
 * normal controls; the server refuses writes either way.
 */
export function useReadOnly(): boolean {
  const state = useAsyncResource(() => getCapabilities());
  return state.phase === "ready" && state.data.read_only;
}
