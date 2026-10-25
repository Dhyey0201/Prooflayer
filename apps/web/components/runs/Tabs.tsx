"use client";

import { useId, useState } from "react";
import type { ReactNode } from "react";

export interface TabDef {
  id: string;
  label: string;
  content: ReactNode;
}

/** Accessible tabs: click or Left/Right/Home/End to switch, one panel mounted at a time. */
export function Tabs({ tabs }: { tabs: TabDef[] }) {
  const [activeId, setActiveId] = useState(tabs[0]?.id);
  const baseId = useId();
  const active = tabs.find((tab) => tab.id === activeId) ?? tabs[0];

  function onKeyDown(event: React.KeyboardEvent, index: number) {
    const lastIndex = tabs.length - 1;
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = index === lastIndex ? 0 : index + 1;
    else if (event.key === "ArrowLeft") nextIndex = index === 0 ? lastIndex : index - 1;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = lastIndex;
    if (nextIndex === null) return;
    event.preventDefault();
    const next = tabs[nextIndex];
    setActiveId(next.id);
    document.getElementById(`${baseId}-tab-${next.id}`)?.focus();
  }

  if (!active) return null;

  return (
    <div>
      <div role="tablist" aria-label="Run detail" className="flex gap-1 border-b border-border">
        {tabs.map((tab, index) => {
          const isSelected = tab.id === active.id;
          return (
            <button
              key={tab.id}
              id={`${baseId}-tab-${tab.id}`}
              role="tab"
              type="button"
              aria-selected={isSelected}
              aria-controls={`${baseId}-panel-${tab.id}`}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => setActiveId(tab.id)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                isSelected
                  ? "border-b-2 border-accent text-foreground"
                  : "border-b-2 border-transparent text-muted hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      <div
        id={`${baseId}-panel-${active.id}`}
        role="tabpanel"
        aria-labelledby={`${baseId}-tab-${active.id}`}
        tabIndex={0}
        className="pt-4"
      >
        {active.content}
      </div>
    </div>
  );
}
