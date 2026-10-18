import type { RunStatus, Verdict } from "@/lib/api/types";

type PillTone = "neutral" | "info" | "success" | "danger" | "warning";

const STATUS_TONE: Record<RunStatus, PillTone> = {
  created: "neutral",
  queued: "neutral",
  provisioning: "info",
  running: "info",
  verifying: "info",
  verified: "success",
  failed: "danger",
  inconclusive: "warning",
  canceled: "neutral",
  error: "danger",
};

const VERDICT_TONE: Record<Exclude<Verdict, null>, PillTone> = {
  VERIFIED: "success",
  FAILED: "danger",
  INCONCLUSIVE: "warning",
};

const TONE_CLASSES: Record<PillTone, string> = {
  neutral: "bg-slate-500/15 text-slate-300 ring-1 ring-inset ring-slate-500/30",
  info: "bg-sky-500/15 text-sky-300 ring-1 ring-inset ring-sky-500/30",
  success: "bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-500/30",
  danger: "bg-rose-500/15 text-rose-300 ring-1 ring-inset ring-rose-500/30",
  warning: "bg-amber-500/15 text-amber-300 ring-1 ring-inset ring-amber-500/30",
};

function PillBase({ tone, label }: { tone: PillTone; label: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${TONE_CLASSES[tone]}`}
    >
      {label}
    </span>
  );
}

export function RunStatusPill({ status }: { status: RunStatus }) {
  return <PillBase tone={STATUS_TONE[status]} label={status} />;
}

export function VerdictPill({ verdict }: { verdict: Verdict }) {
  if (verdict === null || verdict === undefined) {
    return <PillBase tone="neutral" label="no verdict" />;
  }
  return <PillBase tone={VERDICT_TONE[verdict]} label={verdict} />;
}
