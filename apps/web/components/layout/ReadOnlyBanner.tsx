"use client";

import { getCapabilities } from "@/lib/api/client";
import { useAsyncResource } from "@/lib/api/useAsyncResource";

/**
 * Shown only when the backend itself reports `read_only` (hosted replay).
 * Loading or a failed fetch renders nothing here; the status panel already
 * reports API errors.
 */
export function ReadOnlyBanner() {
  const state = useAsyncResource(() => getCapabilities());
  if (state.phase !== "ready" || !state.data.read_only) return null;
  return (
    <div
      role="note"
      className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-200 md:px-8"
    >
      <strong className="font-semibold">Replay:</strong> this hosted demo is a read-only replay of
      recorded runs. Launching runs and requesting challenges are disabled; every result shown was
      recorded from a real run, and its evidence can be re-checked offline.
    </div>
  );
}
