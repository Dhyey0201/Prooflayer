import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

import { Sidebar } from "@/components/layout/Sidebar";

describe("Sidebar navigation", () => {
  it("exposes primary nav links as an accessible, labeled landmark", () => {
    render(<Sidebar />);

    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(nav).toBeInTheDocument();

    const dashboardLink = screen.getByRole("link", { name: "Dashboard" });
    const runsLink = screen.getByRole("link", { name: "Runs" });
    expect(dashboardLink).toHaveAttribute("aria-current", "page");
    expect(runsLink).not.toHaveAttribute("aria-current");
  });

  it("is reachable via keyboard Tab order", async () => {
    const user = userEvent.setup();
    render(<Sidebar />);

    await user.tab();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveFocus();

    await user.tab();
    expect(screen.getByRole("link", { name: "Runs" })).toHaveFocus();
  });
});
