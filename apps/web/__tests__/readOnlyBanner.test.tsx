import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReadOnlyBanner } from "@/components/layout/ReadOnlyBanner";

function capabilities(readOnly: boolean): Response {
  return new Response(
    JSON.stringify({
      mock_mode: false,
      nebius_configured: false,
      live_model_enabled: false,
      openshell_available: false,
      sandbox_enforced: false,
      unenforced_live_allowed: false,
      read_only: readOnly,
      independent_verifier_available: false,
      tavily_enabled: false,
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

describe("ReadOnlyBanner", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("labels a read-only deployment as a replay of recorded runs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(capabilities(true)));
    render(<ReadOnlyBanner />);
    expect(await screen.findByRole("note")).toHaveTextContent("read-only replay of recorded runs");
  });

  it("renders nothing when the backend accepts writes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(capabilities(false));
    vi.stubGlobal("fetch", fetchMock);
    render(<ReadOnlyBanner />);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });
});
