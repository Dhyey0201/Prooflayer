import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BenchmarkReportView, formatRatio } from "@/components/benchmark/BenchmarkReportView";
import type { BenchmarkReport } from "@/lib/api/types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function report(overrides: Partial<BenchmarkReport> = {}): BenchmarkReport {
  return {
    schema_version: "0.1.0",
    generated_at: "2026-10-29T21:06:35Z",
    seed_count: 18,
    passes: 3,
    deterministic: true,
    all_expectations_met: true,
    mismatched_cases: [],
    metrics: {
      detection_recall: { value: 0.8333, numerator: 5, denominator: 6, definition: "flagged / seeded" },
      malicious_challenges_blocked: { value: null, numerator: 0, denominator: 0, definition: "none seeded" },
    },
    verification_overhead: {
      samples: 54,
      verification_ms_median: 1479.4,
      verification_ms_p95: 30376,
      definition: "agent.finished to certificate.issued",
    },
    secret_scan: { matches: 0, bytes_scanned: 963948 },
    environment: {
      platform: "Darwin arm64",
      sandbox: { driver: "mock", enforced: false },
      verifier: { driver: "docker", isolation: "container", network: "none", image_id: null },
      model: { provider: "scripted", model_id: "prooflayer/scripted-fixture-agent-0.1" },
    },
    limitations: ["Agents are scripted model replies, not a live model."],
    ...overrides,
  };
}

describe("BenchmarkReportView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders measured ratios with their counts and a null ratio as n/a", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(report())));
    render(<BenchmarkReportView />);

    expect(await screen.findByText("83.3%")).toBeInTheDocument();
    expect(screen.getByText("(5/6)")).toBeInTheDocument();
    expect(screen.getByText("n/a")).toBeInTheDocument();
    expect(screen.getByText("1.5 s")).toBeInTheDocument();
    expect(screen.getByText(/\(not enforced\)/)).toBeInTheDocument();
    expect(screen.getByText("Agents are scripted model replies, not a live model.")).toBeInTheDocument();
  });

  it("shows mismatched cases instead of claiming every expectation was met", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(report({ all_expectations_met: false, mismatched_cases: ["B06", "B17"] })),
      ),
    );
    render(<BenchmarkReportView />);
    expect(await screen.findByText("no (B06, B17)")).toBeInTheDocument();
  });

  it("shows the API error, never placeholder numbers, when no report is published", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "not_found", message: "No benchmark report has been published", request_id: "req-1" } },
          404,
        ),
      ),
    );
    render(<BenchmarkReportView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No benchmark report has been published");
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });

  it("formats ratios without inventing precision", () => {
    expect(formatRatio({ value: 1, numerator: 18, denominator: 18, definition: "" })).toBe("100%");
    expect(formatRatio({ value: 0, numerator: 0, denominator: 50, definition: "" })).toBe("0%");
    expect(formatRatio({ value: null, numerator: 0, denominator: 0, definition: "" })).toBe("n/a");
  });
});
