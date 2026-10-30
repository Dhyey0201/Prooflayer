import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardHero } from "@/components/dashboard/DashboardHero";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const ratio = (value: number | null, numerator: number, denominator: number) => ({
  value,
  numerator,
  denominator,
  definition: "",
});

describe("DashboardHero", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows measured headline numbers, including the one with a miss", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          seed_count: 18,
          passes: 3,
          metrics: {
            verdict_accuracy: ratio(1, 18, 18),
            detection_recall: ratio(0.8333, 5, 6),
            claim_mismatch_recall: ratio(1, 4, 4),
            integrity_detection_rate: ratio(1, 85, 85),
          },
        }),
      ),
    );
    render(<DashboardHero />);
    expect(await screen.findByText("83.3%")).toBeInTheDocument();
    expect(screen.getByText("(5/6)")).toBeInTheDocument();
    expect(screen.getByText(/18 seeded cases/)).toBeInTheDocument();
  });

  it("shows no numbers at all when no report is published", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ error: { code: "not_found", message: "none", request_id: "r" } }, 404),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<DashboardHero />);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("is not proof");
  });
});
