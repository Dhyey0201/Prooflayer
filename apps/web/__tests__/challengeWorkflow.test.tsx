import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChallengeWorkflow } from "@/components/runs/ChallengeWorkflow";
import type { Challenge } from "@/lib/api/types";
import { buildCheck, readyCertificateState, RUN_ID } from "./testFixtures";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function baseChallenge(overrides: Partial<Challenge> = {}): Challenge {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    run_id: RUN_ID,
    status: "completed",
    requirement_id: "no-forbidden-access-attempts",
    challenge_type: "pytest_case",
    validated: true,
    outcome: "PASS",
    reason: null,
    test_sha256: "t".repeat(64),
    test_bytes: 200,
    test_count: 1,
    test_source: "def test_extra():\n    assert True\n",
    exit_code: 0,
    output_sha256: "o".repeat(64),
    output_bytes: 10,
    duration_ms: 300,
    provider: "scripted",
    model_id: "prooflayer/scripted-fixture-agent-0.1",
    verifier_image_id: "sha256:" + "f".repeat(64),
    created_at: "2026-10-25T00:00:00Z",
    finished_at: "2026-10-25T00:00:01Z",
    ...overrides,
  };
}

describe("ChallengeWorkflow", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("disables the request button and explains why when the run isn't certified", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    render(
      <ChallengeWorkflow
        runId={RUN_ID}
        canChallenge={false}
        certificate={{ phase: "not_ready" }}
      />,
    );

    expect(await screen.findByText("No challenges requested yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request challenge" })).toBeDisabled();
    expect(screen.getByText("Available once this run is certified.")).toBeInTheDocument();
  });

  it("shows an untrusted test's source as code, never renders it as HTML", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([baseChallenge({ test_source: "<img src=x onerror=alert(1)>" })]),
      ),
    );

    render(
      <ChallengeWorkflow runId={RUN_ID} canChallenge certificate={{ phase: "not_ready" }} />,
    );

    const code = await screen.findByText("<img src=x onerror=alert(1)>");
    expect(code.tagName).toBe("CODE");
    expect(document.querySelector("img")).not.toBeInTheDocument();
  });

  it("marks a rejected proposal as never executed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([
          baseChallenge({
            status: "rejected",
            validated: false,
            outcome: null,
            exit_code: null,
            reason: "disallowed_import",
          }),
        ]),
      ),
    );

    render(
      <ChallengeWorkflow runId={RUN_ID} canChallenge certificate={{ phase: "not_ready" }} />,
    );

    expect(
      await screen.findByText(/Rejected by static validation — never executed/),
    ).toBeInTheDocument();
  });

  it("compares the challenge outcome against the original certificate check", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([
          baseChallenge({ requirement_id: "no-forbidden-access-attempts", outcome: "FAIL" }),
        ]),
      ),
    );
    const certificate = readyCertificateState({
      checks: [buildCheck({ requirement_id: "no-forbidden-access-attempts", outcome: "PASS" })],
    });

    render(<ChallengeWorkflow runId={RUN_ID} canChallenge certificate={certificate} />);

    expect(await screen.findByText("disagree")).toBeInTheDocument();
  });

  it("shows recorded challenges but no request button in a read-only replay", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([baseChallenge()])));

    render(
      <ChallengeWorkflow
        runId={RUN_ID}
        canChallenge
        certificate={readyCertificateState()}
        readOnly
      />,
    );

    expect(await screen.findByText(/new challenges are disabled/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request challenge" })).not.toBeInTheDocument();
    expect(await screen.findByText("Completed")).toBeInTheDocument();
  });

  it("requests a challenge on click and disables the button while active", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([])) // initial list
      .mockResolvedValueOnce(jsonResponse(baseChallenge({ status: "queued" }), 202)) // POST
      .mockResolvedValue(jsonResponse([baseChallenge({ status: "queued" })])); // refetch
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(
      <ChallengeWorkflow runId={RUN_ID} canChallenge certificate={{ phase: "not_ready" }} />,
    );

    const button = await screen.findByRole("button", { name: "Request challenge" });
    await user.click(button);

    expect(await screen.findByText("A challenge is already in progress.")).toBeInTheDocument();
  });

  it("surfaces a failed request without fabricating a queued challenge", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: "conflict", message: "Cannot challenge yet: run_not_certified", request_id: "r1" } },
          409,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<ChallengeWorkflow runId={RUN_ID} canChallenge certificate={{ phase: "not_ready" }} />);

    const button = await screen.findByRole("button", { name: "Request challenge" });
    await user.click(button);

    expect(await screen.findByText(/run_not_certified/)).toBeInTheDocument();
    expect(screen.queryByText("A challenge is already in progress.")).not.toBeInTheDocument();
  });
});
