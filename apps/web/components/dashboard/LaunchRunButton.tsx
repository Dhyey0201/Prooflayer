"use client";

import { useRouter } from "next/navigation";

import { useCreateRun } from "@/lib/api/useCreateRun";
import type { TemplateId } from "@/lib/api/types";

export function LaunchRunButton({ templateId }: { templateId: TemplateId }) {
  const router = useRouter();
  const { launch, state } = useCreateRun();

  async function handleClick() {
    const runId = await launch(templateId);
    if (runId) {
      router.push(`/runs/${runId}`);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        disabled={state.phase === "pending"}
        className="w-full rounded-lg bg-accent px-3 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:cursor-wait disabled:opacity-60"
      >
        {state.phase === "pending" ? "Launching…" : "Launch run"}
      </button>
      {state.phase === "error" && (
        <p role="alert" className="mt-2 text-xs text-rose-300">
          {state.message}
        </p>
      )}
    </div>
  );
}
