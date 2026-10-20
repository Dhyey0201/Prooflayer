export function ErrorPanel({
  message,
  requestId,
  onRetry,
}: {
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-rose-300">Could not load this data</p>
          <p className="mt-1 text-sm text-rose-200/80">{message}</p>
          {requestId && (
            <p className="mt-1 text-xs text-rose-200/60">Request ID: {requestId}</p>
          )}
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="shrink-0 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
