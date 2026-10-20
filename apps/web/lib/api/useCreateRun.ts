"use client";

import { useCallback, useState } from "react";

import { ApiRequestError, createRun } from "./client";
import type { TemplateId } from "./types";

export type LaunchState =
  | { phase: "idle" }
  | { phase: "pending" }
  | { phase: "error"; message: string };

/**
 * Launches a fixture run for a template. Generates a fresh idempotency key
 * per call so a double-click or retry replays the same run instead of
 * creating a duplicate; the caller gets the created run's id to navigate to.
 */
export function useCreateRun() {
  const [state, setState] = useState<LaunchState>({ phase: "idle" });

  const launch = useCallback(async (templateId: TemplateId): Promise<string | null> => {
    setState({ phase: "pending" });
    try {
      const { run } = await createRun(
        { template_id: templateId, mode: "fixture" },
        crypto.randomUUID(),
      );
      setState({ phase: "idle" });
      return run.id;
    } catch (err) {
      setState({
        phase: "error",
        message: err instanceof ApiRequestError ? err.message : "Could not launch the run.",
      });
      return null;
    }
  }, []);

  return { launch, state };
}
