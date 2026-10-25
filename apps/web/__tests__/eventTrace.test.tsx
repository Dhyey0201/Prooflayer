import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { EventTrace } from "@/components/runs/EventTrace";
import type { Event } from "@/lib/api/types";

const EVENTS: Event[] = [
  {
    run_id: "11111111-1111-1111-1111-111111111111",
    seq: 1,
    timestamp: "2026-10-20T00:00:00Z",
    event_type: "run.created",
    actor: "api",
    safe_payload: { template_id: "success-validation", mode: "fixture", policy_version: "0.1.0" },
    previous_hash: "0".repeat(64),
    event_hash: "a".repeat(64),
  },
  {
    run_id: "11111111-1111-1111-1111-111111111111",
    seq: 2,
    timestamp: "2026-10-20T00:00:01Z",
    event_type: "run.status_changed",
    actor: "api",
    safe_payload: { from_status: "created", to_status: "queued", reason: "accepted" },
    previous_hash: "a".repeat(64),
    event_hash: "b".repeat(64),
  },
];

describe("EventTrace", () => {
  it("shows an empty state when there are no events, never a fabricated row", () => {
    render(<EventTrace events={[]} />);
    expect(screen.getByText("No events yet.")).toBeInTheDocument();
  });

  it("selects the first event by default and shows its hashes", () => {
    render(<EventTrace events={EVENTS} />);
    expect(screen.queryByText(/Select an event/)).not.toBeInTheDocument();
    expect(screen.getAllByText("a".repeat(64)).length).toBeGreaterThan(0);
  });

  it("switches the detail panel when a different event is selected", async () => {
    const user = userEvent.setup();
    render(<EventTrace events={EVENTS} />);

    await user.click(screen.getByRole("button", { name: /Status changed/ }));

    const detail = screen.getByRole("region", { name: "Event detail" });
    expect(within(detail).getByText("#2 · Status changed")).toBeInTheDocument();
    expect(within(detail).getByText("b".repeat(64))).toBeInTheDocument();
  });

  it("labels a policy denial and shows it was not runtime-enforced in mock mode", () => {
    const denied: Event = {
      run_id: "11111111-1111-1111-1111-111111111111",
      seq: 3,
      timestamp: "2026-10-20T00:00:02Z",
      event_type: "policy.denied",
      actor: "orchestrator",
      safe_payload: {
        step: 2,
        action: "read_file",
        target: ".env.production",
        enforcement_point: "mock",
        enforced: false,
        source: "mock_policy",
        rule: "read_denied_paths",
      },
      previous_hash: "b".repeat(64),
      event_hash: "c".repeat(64),
    };
    render(<EventTrace events={[...EVENTS, denied]} />);
    expect(screen.getByText("Policy denied")).toBeInTheDocument();
    expect(
      screen.getByText("action=read_file target=.env.production enforced=false source=mock_policy"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/undefined/)).not.toBeInTheDocument();
  });

  it("labels verifier check results with their measured outcome and exit code", () => {
    const check: Event = {
      run_id: "11111111-1111-1111-1111-111111111111",
      seq: 3,
      timestamp: "2026-10-23T00:00:02Z",
      event_type: "check.completed",
      actor: "verifier",
      safe_payload: {
        requirement_id: "pytest-full-suite",
        kind: "pytest",
        outcome: "FAIL",
        reason: "tests_failed",
        exit_code: 1,
        image_id: "sha256:" + "d".repeat(64),
      },
      previous_hash: "b".repeat(64),
      event_hash: "e".repeat(64),
    };
    render(<EventTrace events={[...EVENTS, check]} />);
    expect(screen.getByText("Independent check")).toBeInTheDocument();
    expect(
      screen.getByText("requirement_id=pytest-full-suite outcome=FAIL exit_code=1 reason=tests_failed"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/undefined/)).not.toBeInTheDocument();
  });
});
