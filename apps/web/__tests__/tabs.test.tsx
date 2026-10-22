import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Tabs } from "@/components/runs/Tabs";

function renderTabs() {
  return render(
    <Tabs
      tabs={[
        { id: "a", label: "Alpha", content: <p>Alpha panel</p> },
        { id: "b", label: "Beta", content: <p>Beta panel</p> },
        { id: "c", label: "Gamma", content: <p>Gamma panel</p> },
      ]}
    />,
  );
}

describe("Tabs", () => {
  it("shows only the first tab's panel by default, marked selected", () => {
    renderTabs();
    expect(screen.getByText("Alpha panel")).toBeInTheDocument();
    expect(screen.queryByText("Beta panel")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Alpha" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Beta" })).toHaveAttribute("aria-selected", "false");
  });

  it("switches panels on click", async () => {
    const user = userEvent.setup();
    renderTabs();

    await user.click(screen.getByRole("tab", { name: "Beta" }));

    expect(screen.getByText("Beta panel")).toBeInTheDocument();
    expect(screen.queryByText("Alpha panel")).not.toBeInTheDocument();
  });

  it("supports Left/Right/End arrow-key navigation with roving focus", async () => {
    const user = userEvent.setup();
    renderTabs();

    screen.getByRole("tab", { name: "Alpha" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Beta" })).toHaveFocus();
    expect(screen.getByText("Beta panel")).toBeInTheDocument();

    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Alpha" })).toHaveFocus();

    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Gamma" })).toHaveFocus();
    expect(screen.getByText("Gamma panel")).toBeInTheDocument();
  });
});
