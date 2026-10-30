"use client";

import { useId, useState } from "react";

import { LaunchRunButton } from "@/components/dashboard/LaunchRunButton";
import { PolicyPreview } from "@/components/dashboard/PolicyPreview";
import type { Template, TemplateId } from "@/lib/api/types";

/** What each seeded scenario exercises; a label for the fixture, never a run result. */
const SCENARIO_STYLE: Record<TemplateId, { tag: string; tone: string; icon: string }> = {
  "success-validation": {
    tag: "Honest fix",
    tone: "from-emerald-400/70 text-emerald-300 bg-emerald-500/10 ring-emerald-500/30",
    icon: "M5 13l4 4L19 7",
  },
  "false-success-auth": {
    tag: "False claim",
    tone: "from-rose-400/70 text-rose-300 bg-rose-500/10 ring-rose-500/30",
    icon: "M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  },
  "denied-secret-read": {
    tag: "Policy attempt",
    tone: "from-amber-400/70 text-amber-300 bg-amber-500/10 ring-amber-500/30",
    icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
  },
};

const FALLBACK_STYLE = {
  tag: "Scenario",
  tone: "from-sky-400/70 text-sky-300 bg-sky-500/10 ring-sky-500/30",
  icon: "M9 12h6m-6 4h6M7 4h10a2 2 0 012 2v12a2 2 0 01-2 2H7a2 2 0 01-2-2V6a2 2 0 012-2z",
};

export function ScenarioCard({ template }: { template: Template }) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const previewId = useId();
  const style = SCENARIO_STYLE[template.id] ?? FALLBACK_STYLE;
  const [gradient, ...chip] = style.tone.split(" ");

  return (
    <article className="group relative flex h-full flex-col justify-between overflow-hidden rounded-xl border border-border bg-surface/70 p-5 transition duration-200 hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-lg hover:shadow-sky-950/40 motion-reduce:transform-none">
      <div
        aria-hidden
        className={`absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r ${gradient} to-transparent`}
      />
      <div>
        <div className="flex items-center justify-between gap-3">
          <span
            aria-hidden
            className={`flex h-9 w-9 items-center justify-center rounded-lg ring-1 ring-inset ${chip.join(" ")}`}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
            >
              <path d={style.icon} />
            </svg>
          </span>
          <span
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${chip.join(" ")}`}
          >
            {style.tag}
          </span>
        </div>
        <h3 className="mt-4 text-base font-semibold text-foreground">{template.title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-foreground/75">{template.description}</p>
        <button
          type="button"
          onClick={() => setPreviewOpen((open) => !open)}
          aria-expanded={previewOpen}
          aria-controls={previewId}
          className="mt-3 text-xs font-medium text-accent hover:underline"
        >
          {previewOpen ? "Hide policy preview" : "Review policy preview"}
        </button>
        {previewOpen && (
          <div id={previewId}>
            <PolicyPreview template={template} />
          </div>
        )}
      </div>
      <div className="mt-5">
        <LaunchRunButton templateId={template.id} />
      </div>
    </article>
  );
}
