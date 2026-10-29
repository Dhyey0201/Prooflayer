import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiRequestError,
  cancelRun,
  createRun,
  getCapabilities,
  getHealth,
  getRun,
  getRunEvents,
  listRuns,
} from "@/lib/api/client";
import type { Event, Run } from "@/lib/api/types";

function jsonResponse(body: unknown, status = 200, headers?: Record<string, string>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

const SAMPLE_RUN: Run = {
  id: "11111111-1111-1111-1111-111111111111",
  template_id: "success-validation",
  status: "queued",
  mode: "fixture",
  created_at: "2026-10-20T00:00:00Z",
  updated_at: "2026-10-20T00:00:01Z",
  agent_claim: null,
  verdict: null,
};

const SAMPLE_EVENT: Event = {
  run_id: SAMPLE_RUN.id,
  seq: 1,
  timestamp: "2026-10-20T00:00:00Z",
  event_type: "run.created",
  actor: "api",
  safe_payload: { template_id: "success-validation", mode: "fixture", policy_version: "0.1.0" },
  previous_hash: "0".repeat(64),
  event_hash: "a".repeat(64),
};

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses a healthy /health response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ status: "ok" })),
    );

    const health = await getHealth();
    expect(health).toEqual({ status: "ok" });
  });

  it("parses /capabilities boolean flags", async () => {
    const capabilities = {
      mock_mode: true,
      nebius_configured: false,
      live_model_enabled: false,
      openshell_available: false,
      sandbox_enforced: false,
      unenforced_live_allowed: false,
      independent_verifier_available: false,
      tavily_enabled: false,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(capabilities)));

    await expect(getCapabilities()).resolves.toEqual(capabilities);
  });

  it("throws a typed ApiRequestError on the backend's error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "not_found", message: "Run not found", request_id: "abc123" } },
          404,
        ),
      ),
    );

    await expect(getHealth()).rejects.toMatchObject({
      name: "ApiRequestError",
      status: 404,
      code: "not_found",
      requestId: "abc123",
    });
  });

  it("never fabricates success when the network request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));

    await expect(getHealth()).rejects.toBeInstanceOf(ApiRequestError);
  });

  it("lists runs newest-first and sends the limit query param", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([SAMPLE_RUN]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listRuns(5)).resolves.toEqual([SAMPLE_RUN]);
    expect(fetchMock.mock.calls[0][0]).toContain("/runs?limit=5");
  });

  it("creates a run with the Idempotency-Key header and reports no replay on first create", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(SAMPLE_RUN, 201));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createRun(
      { template_id: "success-validation", mode: "fixture" },
      "test-key-00000001",
    );

    expect(result).toEqual({ run: SAMPLE_RUN, replayed: false });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("test-key-00000001");
    expect(init.body).toBe(
      JSON.stringify({ template_id: "success-validation", mode: "fixture" }),
    );
  });

  it("reports a replay when the backend sends Idempotent-Replayed: true", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(SAMPLE_RUN, 201, { "Idempotent-Replayed": "true" }),
      ),
    );

    const result = await createRun(
      { template_id: "success-validation", mode: "fixture" },
      "test-key-00000001",
    );

    expect(result.replayed).toBe(true);
  });

  it("surfaces 429 (too many pending runs) as a typed error, not a fabricated run", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "rate_limited", message: "Too many pending runs; retry later", request_id: "r1" } },
          429,
        ),
      ),
    );

    await expect(
      createRun({ template_id: "success-validation", mode: "fixture" }, "test-key-00000002"),
    ).rejects.toMatchObject({ status: 429, code: "rate_limited" });
  });

  it("surfaces 409 (Idempotency-Key reused with a different body) as a typed error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "conflict",
              message: "Idempotency-Key was already used with a different request",
              request_id: "r2",
            },
          },
          409,
        ),
      ),
    );

    await expect(
      createRun({ template_id: "false-success-auth", mode: "fixture" }, "test-key-00000003"),
    ).rejects.toMatchObject({ status: 409, code: "conflict" });
  });

  it("fetches a single run by id", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(SAMPLE_RUN)));

    await expect(getRun(SAMPLE_RUN.id)).resolves.toEqual(SAMPLE_RUN);
  });

  it("fetches run events with after_seq for incremental polling", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([SAMPLE_EVENT]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getRunEvents(SAMPLE_RUN.id, 1)).resolves.toEqual([SAMPLE_EVENT]);
    expect(fetchMock.mock.calls[0][0]).toContain(`/runs/${SAMPLE_RUN.id}/events?after_seq=1`);
  });

  it("cancels a run", async () => {
    const canceled: Run = { ...SAMPLE_RUN, status: "canceled" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(canceled, 202)));

    await expect(cancelRun(SAMPLE_RUN.id)).resolves.toEqual(canceled);
  });

  it("surfaces a 404 for an unknown run id rather than an empty success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: "not_found", message: "Run not found", request_id: null } }, 404),
      ),
    );

    await expect(getRun("00000000-0000-0000-0000-000000000000")).rejects.toMatchObject({
      status: 404,
      code: "not_found",
    });
  });
});
