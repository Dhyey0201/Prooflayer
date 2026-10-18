import type { Run } from "../api/types";

/**
 * Local sample data standing in for `GET /api/v1/runs`, which is not
 * implemented until Commit 03 (see docs/03_SEVEN_DAY_COMMIT_PLAN.md). Every
 * consumer of this module must surface the `isSample` flag to the user —
 * never render these as live backend results.
 */
export interface SampleRun extends Run {
  isSample: true;
}

export const SAMPLE_RUNS: SampleRun[] = [
  {
    isSample: true,
    id: "00000000-0000-0000-0000-000000000001",
    template_id: "success-validation",
    status: "verified",
    mode: "fixture",
    created_at: "2026-10-18T09:00:00Z",
    updated_at: "2026-10-18T09:02:14Z",
    agent_claim: "All pinned tests passed.",
    verdict: "VERIFIED",
  },
  {
    isSample: true,
    id: "00000000-0000-0000-0000-000000000002",
    template_id: "false-success-auth",
    status: "failed",
    mode: "fixture",
    created_at: "2026-10-18T09:10:00Z",
    updated_at: "2026-10-18T09:13:47Z",
    agent_claim: "Selected tests passed; task complete.",
    verdict: "FAILED",
  },
  {
    isSample: true,
    id: "00000000-0000-0000-0000-000000000003",
    template_id: "denied-secret-read",
    status: "inconclusive",
    mode: "fixture",
    created_at: "2026-10-18T09:20:00Z",
    updated_at: "2026-10-18T09:21:05Z",
    agent_claim: "Read configuration to verify deployment settings.",
    verdict: "INCONCLUSIVE",
  },
];
