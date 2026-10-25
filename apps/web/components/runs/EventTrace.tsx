"use client";

import { useState } from "react";

import type { Event } from "@/lib/api/types";

const EVENT_LABELS: Record<Event["event_type"], string> = {
  "run.created": "Run created",
  "run.status_changed": "Status changed",
  "sandbox.provisioned": "Sandbox provisioned",
  "sandbox.released": "Sandbox released",
  "model.called": "Model called",
  "agent.action_proposed": "Agent proposed action",
  "tool.result": "Tool result",
  "policy.denied": "Policy denied",
  "agent.claimed": "Agent claim (untrusted)",
  "agent.finished": "Agent finished",
  "workspace.snapshot": "Workspace snapshot",
  "check.completed": "Independent check",
  "certificate.issued": "Certificate issued",
  "challenge.requested": "Challenge requested",
  "challenge.proposed": "Challenge proposed (untrusted test)",
  "challenge.rejected": "Challenge rejected",
  "challenge.completed": "Challenge executed",
};

// Fields shown inline for the newer event types, in this order when present.
const SUMMARY_FIELDS = [
  "requirement_id",
  "action",
  "target",
  "outcome",
  "verdict",
  "exit_code",
  "driver",
  "enforced",
  "source",
  "reason",
];

function formatTime(value: string): string {
  return new Date(value).toLocaleTimeString(undefined, { hour12: false });
}

function EventSummary({ event }: { event: Event }) {
  if (event.event_type === "run.status_changed") {
    const { from_status, to_status } = event.safe_payload;
    return (
      <span className="font-mono text-xs text-muted">
        {String(from_status)} &rarr; {String(to_status)}
      </span>
    );
  }
  if (event.event_type === "run.created") {
    return (
      <span className="font-mono text-xs text-muted">
        {String(event.safe_payload.template_id)} ({String(event.safe_payload.mode)})
      </span>
    );
  }
  const parts = SUMMARY_FIELDS.filter((key) => key in event.safe_payload).map(
    (key) => `${key}=${String(event.safe_payload[key])}`,
  );
  return <span className="font-mono text-xs text-muted">{parts.join(" ")}</span>;
}

export function EventTrace({ events }: { events: Event[] }) {
  const [selectedSeq, setSelectedSeq] = useState<number | null>(events[0]?.seq ?? null);
  const selected = events.find((event) => event.seq === selectedSeq) ?? null;

  if (events.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">
        No events yet.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <ol aria-label="Event trace" className="space-y-2">
        {events.map((event) => {
          const isSelected = event.seq === selectedSeq;
          return (
            <li key={event.seq}>
              <button
                type="button"
                onClick={() => setSelectedSeq(event.seq)}
                aria-current={isSelected ? "true" : undefined}
                aria-controls="event-detail-panel"
                className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                  isSelected
                    ? "border-accent/50 bg-accent/10"
                    : "border-border bg-surface/60 hover:border-accent/30"
                }`}
              >
                <span className="flex items-center gap-2">
                  <span className="font-mono text-xs text-muted">#{event.seq}</span>
                  <span className="font-medium text-foreground">
                    {EVENT_LABELS[event.event_type]}
                  </span>
                </span>
                <EventSummary event={event} />
              </button>
            </li>
          );
        })}
      </ol>

      <div
        id="event-detail-panel"
        role="region"
        aria-label="Event detail"
        className="rounded-xl border border-border bg-surface/60 p-4"
      >
        {selected ? (
          <dl className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <dt className="font-semibold text-foreground">
                #{selected.seq} &middot; {EVENT_LABELS[selected.event_type]}
              </dt>
              <dd className="text-xs text-muted">{formatTime(selected.timestamp)}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted">Actor</dt>
              <dd className="font-mono text-xs text-foreground">{selected.actor}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted">Payload</dt>
              <dd>
                <pre className="mt-1 overflow-x-auto rounded-lg bg-background p-3 text-xs text-foreground/90">
                  {JSON.stringify(selected.safe_payload, null, 2)}
                </pre>
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted">Previous hash</dt>
              <dd className="break-all font-mono text-xs text-muted">{selected.previous_hash}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted">Event hash</dt>
              <dd className="break-all font-mono text-xs text-muted">{selected.event_hash}</dd>
            </div>
          </dl>
        ) : (
          <p className="text-sm text-muted">Select an event to see its evidence.</p>
        )}
      </div>
    </div>
  );
}
