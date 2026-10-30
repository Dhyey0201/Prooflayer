import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { ScenarioCard } from "@/components/dashboard/ScenarioCard";
import type { Template } from "@/lib/api/types";

const TEMPLATE: Template = {
  id: "false-success-auth",
  title: "Token refresh fix (false success)",
  description: "Agent updates token refresh logic.",
  allowed_paths: ["src/auth.py"],
  read_denied_paths: [],
  required_checks: ["pytest-full-suite"],
  policy_version: "0.1.0",
  repo_sha: "a".repeat(64),
  expected_verdict: "FAILED",
};

describe("ScenarioCard", () => {
  it("offers to launch a run on a writable backend", () => {
    render(<ScenarioCard template={TEMPLATE} />);
    expect(screen.getByRole("button", { name: "Launch run" })).toBeInTheDocument();
  });

  it("links to the recorded run instead of launching in a read-only replay", () => {
    render(<ScenarioCard template={TEMPLATE} readOnly recordedRunId="run-123" />);
    expect(screen.queryByRole("button", { name: "Launch run" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the recorded run" })).toHaveAttribute(
      "href",
      "/runs/run-123",
    );
  });

  it("says so when a read-only replay has no recorded run for the scenario", () => {
    render(<ScenarioCard template={TEMPLATE} readOnly recordedRunId={null} />);
    expect(screen.queryByRole("button")).not.toHaveTextContent("Launch run");
    expect(screen.getByText("No recorded run for this scenario.")).toBeInTheDocument();
  });
});
