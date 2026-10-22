import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CertificateExplorer } from "@/components/runs/CertificateExplorer";
import type { Certificate } from "@/lib/api/types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const RUN_ID = "11111111-1111-1111-1111-111111111111";

function certificate(verdict: Certificate["verdict"]): Certificate {
  return {
    schema_version: "0.1.0",
    run_id: RUN_ID,
    verdict,
    claims: [{ requirement_id: "r1", summary: "agent claims success" }],
    checks: [
      { requirement_id: "pytest-full-suite", outcome: "FAIL" },
      { requirement_id: "diff-within-allowlist", outcome: "PASS" },
      { requirement_id: "no-forbidden-access-attempts", outcome: "INCONCLUSIVE" },
    ],
    evidence_manifest_sha256: "e".repeat(64),
    limitations: ["sandbox not OpenShell-enforced on this host"],
  };
}

describe("CertificateExplorer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows 'no certificate yet' on a 404, never a fabricated result", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: "not_found", message: "Not Found", request_id: null } }, 404),
      ),
    );

    render(<CertificateExplorer runId={RUN_ID} />);

    expect(await screen.findByText("No certificate yet")).toBeInTheDocument();
    // No certificate means no verdict pill and no export action — not a fabricated result.
    expect(screen.queryByRole("button", { name: "Download JSON" })).not.toBeInTheDocument();
  });

  it("surfaces a non-404 failure as an explicit error, not a silent 'not ready'", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));

    render(<CertificateExplorer runId={RUN_ID} />);

    expect(await screen.findByText(/Could not load this data/)).toBeInTheDocument();
  });

  it.each([
    ["VERIFIED" as const],
    ["FAILED" as const],
    ["INCONCLUSIVE" as const],
  ])("renders the %s verdict and surfaces the evidence manifest hash", async (verdict) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(certificate(verdict))));

    render(<CertificateExplorer runId={RUN_ID} />);

    // `INCONCLUSIVE` is also a possible check outcome, so more than one match
    // is valid — assert at least one, not exactly one.
    await screen.findAllByText(verdict);
    expect(screen.getAllByText(verdict).length).toBeGreaterThan(0);
    expect(screen.getByText("e".repeat(64))).toBeInTheDocument();
  });

  it("renders PASS/FAIL/INCONCLUSIVE outcomes in the checks table with accessible labels", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(certificate("FAILED"))));

    render(<CertificateExplorer runId={RUN_ID} />);

    await screen.findByText("FAILED");
    expect(screen.getByText("PASS")).toBeInTheDocument();
    expect(screen.getByText("FAIL")).toBeInTheDocument();
    expect(screen.getByText("INCONCLUSIVE")).toBeInTheDocument();
  });

  it("exports the certificate as a downloaded JSON file", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(certificate("VERIFIED"))));
    const createObjectURL = vi.fn().mockReturnValue("blob:mock");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    const user = userEvent.setup();
    render(<CertificateExplorer runId={RUN_ID} />);
    await screen.findByText("VERIFIED");

    await user.click(screen.getByRole("button", { name: "Download JSON" }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("application/json");
    const text = await blob.text();
    expect(JSON.parse(text)).toMatchObject({ run_id: RUN_ID, verdict: "VERIFIED" });
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock");
  });
});
