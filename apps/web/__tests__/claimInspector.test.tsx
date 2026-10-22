import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ClaimInspector } from "@/components/runs/ClaimInspector";
import type { Event, Run, Template } from "@/lib/api/types";

const RUN_ID = "11111111-1111-1111-1111-111111111111";

const TEMPLATE: Template = {
  id: "denied-secret-read",
  title: "Auth refactor with denied secret read",
  description: "test fixture",
  allowed_paths: ["src/auth.py"],
  read_denied_paths: [".env.production"],
  required_checks: ["pytest-full-suite", "no-forbidden-access-attempts"],
  policy_version: "0.1.0",
  repo_sha: "unpinned",
  expected_verdict: "FAILED",
};

function baseRun(overrides: Partial<Run> = {}): Run {
  return {
    id: RUN_ID,
    template_id: "denied-secret-read",
    status: "verifying",
    mode: "fixture",
    created_at: "2026-10-21T00:00:00Z",
    updated_at: "2026-10-21T00:00:01Z",
    agent_claim: null,
    verdict: null,
    ...overrides,
  };
}

function policyDeniedEvent(seq: number): Event {
  return {
    run_id: RUN_ID,
    seq,
    timestamp: "2026-10-21T00:00:00Z",
    event_type: "policy.denied",
    actor: "orchestrator",
    safe_payload: {
      step: seq,
      action: "read_file",
      target: ".env.production",
      enforcement_point: "mock",
      enforced: false,
      source: "mock_policy",
      rule: "read_denied_paths",
    },
    previous_hash: "0".repeat(64),
    event_hash: `${seq}`.repeat(64).slice(0, 64),
  };
}

function claimedEvent(seq: number, testsPassed: boolean): Event {
  return {
    run_id: RUN_ID,
    seq,
    timestamp: "2026-10-21T00:00:02Z",
    event_type: "agent.claimed",
    actor: "orchestrator",
    safe_payload: {
      claim_sha256: "deadbeef".repeat(8),
      claim_chars: 42,
      tests_passed: testsPassed,
    },
    previous_hash: "0".repeat(64),
    event_hash: "a".repeat(64),
  };
}

describe("ClaimInspector", () => {
  it("never fabricates a claim when there is none (missing event safety)", () => {
    render(<ClaimInspector run={baseRun()} events={[]} template={TEMPLATE} />);
    expect(screen.getByText("No agent claim yet.")).toBeInTheDocument();
  });

  it("shows the agent's claim as explicitly untrusted, with its hash and length", () => {
    const run = baseRun({ agent_claim: "All tests passed." });
    render(
      <ClaimInspector run={run} events={[claimedEvent(1, true)]} template={TEMPLATE} />,
    );

    expect(screen.getByText("Agent claim — untrusted")).toBeInTheDocument();
    expect(screen.getByText("All tests passed.")).toBeInTheDocument();
    expect(screen.getByText("passed")).toBeInTheDocument();
    expect(screen.getByText("42 chars")).toBeInTheDocument();
  });

  it("lists every required check as INCONCLUSIVE, never a fabricated PASS/FAIL", () => {
    render(<ClaimInspector run={baseRun()} events={[]} template={TEMPLATE} />);

    const pills = screen.getAllByText(/INCONCLUSIVE/);
    expect(pills.length).toBe(TEMPLATE.required_checks.length);
    const panel = screen.getByText("Evidence status per required check").closest("div")!;
    expect(within(panel).getByText("pytest-full-suite")).toBeInTheDocument();
    expect(within(panel).getByText("no-forbidden-access-attempts")).toBeInTheDocument();
  });

  it("surfaces the real count of observed forbidden-access attempts", () => {
    render(
      <ClaimInspector
        run={baseRun()}
        events={[policyDeniedEvent(1), policyDeniedEvent(2)]}
        template={TEMPLATE}
      />,
    );

    expect(screen.getByText(/2 forbidden attempts observed, all denied/)).toBeInTheDocument();
  });

  it("degrades gracefully when the template could not be loaded", () => {
    render(<ClaimInspector run={baseRun()} events={[]} template={null} />);
    expect(screen.getByText(/Requirements unavailable/)).toBeInTheDocument();
    // No evidence-status panel without a template to source required_checks from.
    expect(screen.queryByText(/not independently measured/)).not.toBeInTheDocument();
  });

  it("colors INCONCLUSIVE but never relies on color alone for the label", () => {
    render(<ClaimInspector run={baseRun()} events={[]} template={TEMPLATE} />);
    const [pill] = screen.getAllByText(/INCONCLUSIVE/);
    expect(within(pill.closest("span") ?? pill).getByText(/INCONCLUSIVE/)).toBeInTheDocument();
  });
});
