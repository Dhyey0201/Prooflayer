"use client";

import { useId, useState } from "react";

import { LaunchRunButton } from "@/components/dashboard/LaunchRunButton";
import { PolicyPreview } from "@/components/dashboard/PolicyPreview";
import type { Template } from "@/lib/api/types";

export function ScenarioCard({ template }: { template: Template }) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const previewId = useId();

  return (
    <article className="flex h-full flex-col justify-between rounded-xl border border-border bg-surface/60 p-5 transition-colors hover:border-accent/40">
      <div>
        <h3 className="text-base font-semibold text-foreground">{template.title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-foreground/80">
          {template.description}
        </p>
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
      <div className="mt-4">
        <LaunchRunButton templateId={template.id} />
      </div>
    </article>
  );
}
