export function SampleDataBadge({ label = "Sample data" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/40 bg-amber-400/10 px-2.5 py-0.5 text-xs font-medium text-amber-300">
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-amber-400" />
      {label} — not a live backend result
    </span>
  );
}
