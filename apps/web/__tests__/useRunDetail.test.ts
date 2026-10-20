import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useRunDetail } from "@/lib/api/useRunDetail";
import type { Event, Run } from "@/lib/api/types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const RUN_ID = "11111111-1111-1111-1111-111111111111";

function run(status: Run["status"]): Run {
  return {
    id: RUN_ID,
    template_id: "success-validation",
    status,
    mode: "fixture",
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-20T00:00:01Z",
    agent_claim: null,
    verdict: null,
  };
}

function event(seq: number): Event {
  return {
    run_id: RUN_ID,
    seq,
    timestamp: "2026-10-20T00:00:00Z",
    event_type: "run.status_changed",
    actor: "api",
    safe_payload: { from_status: "created", to_status: "queued", reason: "accepted" },
    previous_hash: "0".repeat(64),
    event_hash: `${seq}`.repeat(64).slice(0, 64),
  };
}

describe("useRunDetail", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("stops polling once the run reaches a terminal status", async () => {
    const fetchMock = vi.fn();
    // Poll 1: active, one event.
    fetchMock.mockResolvedValueOnce(jsonResponse(run("queued")));
    fetchMock.mockResolvedValueOnce(jsonResponse([event(1)]));
    // Poll 2: terminal, one more event — polling should stop after this.
    fetchMock.mockResolvedValueOnce(jsonResponse(run("canceled")));
    fetchMock.mockResolvedValueOnce(jsonResponse([event(2)]));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useRunDetail(RUN_ID));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.phase).toBe("ready");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(result.current.phase === "ready" && result.current.run.status).toBe("canceled");
    expect(result.current.phase === "ready" && result.current.events).toHaveLength(2);

    // Terminal: a further tick must not issue more requests.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("surfaces a fetch failure as an explicit error, never stale fabricated data", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("network down"));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useRunDetail(RUN_ID));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.phase).toBe("error");
  });
});
