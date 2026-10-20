"use client";

import { getCapabilities, getHealth } from "./client";
import { useAsyncResource } from "./useAsyncResource";
import type { CapabilitiesResponse, HealthResponse } from "./types";

export interface SystemStatus {
  health: HealthResponse;
  capabilities: CapabilitiesResponse;
}

async function fetchSystemStatus(): Promise<SystemStatus> {
  const [health, capabilities] = await Promise.all([getHealth(), getCapabilities()]);
  return { health, capabilities };
}

/**
 * Fetches `/health` and `/capabilities` from the real backend on mount.
 * Never reads fixture data and never falls back to a fabricated "ok" state
 * on failure — a failed fetch stays an explicit error.
 */
export function useSystemStatus() {
  return useAsyncResource<SystemStatus>(fetchSystemStatus);
}
