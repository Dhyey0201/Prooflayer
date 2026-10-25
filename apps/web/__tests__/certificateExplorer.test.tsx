import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CertificateExplorer } from "@/components/runs/CertificateExplorer";
import type { CertificateState } from "@/lib/api/useCertificate";
import { buildCheck, readyCertificateState } from "./testFixtures";

describe("CertificateExplorer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows 'no certificate yet' when not ready, never a fabricated result", () => {
    render(<CertificateExplorer certificate={{ phase: "not_ready" }} />);

    expect(screen.getByText("No certificate yet")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download JSON" })).not.toBeInTheDocument();
  });

  it("surfaces a real fetch failure as an explicit error", () => {
    const state: CertificateState = {
      phase: "error",
      message: "network down",
      requestId: null,
    };
    render(<CertificateExplorer certificate={state} />);

    expect(screen.getByText(/Could not load this data/)).toBeInTheDocument();
  });

  it.each([["VERIFIED" as const], ["FAILED" as const], ["INCONCLUSIVE" as const]])(
    "renders the %s verdict and surfaces the evidence manifest hash",
    (verdict) => {
      render(<CertificateExplorer certificate={readyCertificateState({ verdict })} />);

      expect(screen.getAllByText(verdict).length).toBeGreaterThan(0);
      expect(screen.getByText("m".repeat(64))).toBeInTheDocument();
    },
  );

  it("surfaces the certificate response header hash separately from the manifest hash", () => {
    render(
      <CertificateExplorer
        certificate={readyCertificateState({}, "z".repeat(64))}
      />,
    );

    expect(screen.getByText("m".repeat(64))).toBeInTheDocument();
    expect(screen.getByText("z".repeat(64))).toBeInTheDocument();
  });

  it("renders PASS/FAIL/INCONCLUSIVE check outcomes with accessible labels", () => {
    render(
      <CertificateExplorer
        certificate={readyCertificateState({
          verdict: "FAILED",
          checks: [
            buildCheck({ requirement_id: "a", outcome: "PASS" }),
            buildCheck({ requirement_id: "b", outcome: "FAIL" }),
            buildCheck({ requirement_id: "c", outcome: "INCONCLUSIVE" }),
          ],
        })}
      />,
    );

    expect(screen.getByText("PASS")).toBeInTheDocument();
    expect(screen.getByText("FAIL")).toBeInTheDocument();
    expect(screen.getByText("INCONCLUSIVE")).toBeInTheDocument();
  });

  it("renders the manifest's verifier identity (driver/isolation/network/image)", () => {
    render(<CertificateExplorer certificate={readyCertificateState()} />);

    expect(screen.getByText(/docker \(container, network: none\)/)).toBeInTheDocument();
  });

  it("exports the certificate as a downloaded JSON file", async () => {
    const createObjectURL = vi.fn().mockReturnValue("blob:mock");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    const user = userEvent.setup();
    render(<CertificateExplorer certificate={readyCertificateState({ verdict: "VERIFIED" })} />);

    await user.click(screen.getByRole("button", { name: "Download JSON" }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("application/json");
    const text = await blob.text();
    expect(JSON.parse(text)).toMatchObject({ verdict: "VERIFIED" });
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock");
  });
});
