import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError, getCapabilities, getHealth } from "@/lib/api/client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

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
});
