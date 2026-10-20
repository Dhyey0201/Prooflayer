import { VerdictPill } from "@/components/StatusPill";
import type { Template } from "@/lib/api/types";

function PathList({ label, paths }: { label: string; paths: string[] }) {
  if (paths.length === 0) return null;
  return (
    <div>
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="mt-1 flex flex-wrap gap-1">
        {paths.map((path) => (
          <code
            key={path}
            className="rounded bg-background px-1.5 py-0.5 text-xs text-foreground/90 ring-1 ring-inset ring-border"
          >
            {path}
          </code>
        ))}
      </dd>
    </div>
  );
}

export function PolicyPreview({ template }: { template: Template }) {
  return (
    <dl className="mt-3 space-y-2 border-t border-border pt-3 text-sm">
      <PathList label="Allowed paths" paths={template.allowed_paths} />
      <PathList label="Read-denied paths" paths={template.read_denied_paths} />
      <div>
        <dt className="text-xs font-medium text-muted">Required checks</dt>
        <dd className="mt-1 flex flex-wrap gap-1">
          {template.required_checks.map((check) => (
            <code
              key={check}
              className="rounded bg-background px-1.5 py-0.5 text-xs text-foreground/90 ring-1 ring-inset ring-border"
            >
              {check}
            </code>
          ))}
        </dd>
      </div>
      <div className="flex items-center justify-between pt-1">
        <span className="text-xs text-muted">
          Policy {template.policy_version} &middot; repo {template.repo_sha}
        </span>
        <span className="flex items-center gap-1.5 text-xs text-muted">
          Benchmark ground truth
          <VerdictPill verdict={template.expected_verdict} />
        </span>
      </div>
    </dl>
  );
}
