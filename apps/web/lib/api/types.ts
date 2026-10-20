/**
 * Types mirror `contracts/openapi.yaml` and the backend enums/schemas in
 * `apps/api/prooflayer_api/{enums,schemas}.py`. Keep both in sync when the
 * contract changes; this file never defines new wire shapes on its own.
 */

export type TemplateId =
  | "success-validation"
  | "false-success-auth"
  | "denied-secret-read";

export type RunMode = "fixture" | "live" | "replay";

export type RunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "verifying"
  | "verified"
  | "failed"
  | "inconclusive"
  | "canceled"
  | "error";

/** Statuses the state machine can still move; mirrors ACTIVE_STATUSES in state_machine.py. */
export const ACTIVE_RUN_STATUSES: readonly RunStatus[] = [
  "created",
  "queued",
  "provisioning",
  "running",
  "verifying",
];

export type Verdict = "VERIFIED" | "FAILED" | "INCONCLUSIVE" | null;

export interface HealthResponse {
  status: "ok";
}

/** Boolean availability flags only; never carries secrets, URLs or model IDs. */
export interface CapabilitiesResponse {
  mock_mode: boolean;
  nebius_configured: boolean;
  live_model_enabled: boolean;
  openshell_available: boolean;
  sandbox_enforced: boolean;
  independent_verifier_available: boolean;
  tavily_enabled: boolean;
}

/** A trusted fixture definition. `expected_verdict` is benchmark ground truth, never a run result. */
export interface Template {
  id: TemplateId;
  title: string;
  description: string;
  allowed_paths: string[];
  read_denied_paths: string[];
  required_checks: string[];
  policy_version: string;
  repo_sha: string;
  expected_verdict: Exclude<Verdict, null>;
}

export interface RunCreate {
  template_id: TemplateId;
  mode?: RunMode;
}

export interface Run {
  id: string;
  template_id: string;
  status: RunStatus;
  mode: RunMode;
  created_at: string;
  updated_at: string;
  // Untrusted agent text, shown as a claim; never evidence of success.
  agent_claim: string | null;
  verdict: Verdict;
}

export type EventType = "run.created" | "run.status_changed";

export type EventActor = "api" | "orchestrator" | "seeder";

export interface Event {
  run_id: string;
  seq: number;
  timestamp: string;
  event_type: EventType;
  actor: EventActor;
  safe_payload: Record<string, string | number | boolean | null>;
  previous_hash: string;
  event_hash: string;
}

export type ErrorCode =
  | "bad_request"
  | "validation_error"
  | "not_found"
  | "method_not_allowed"
  | "conflict"
  | "rate_limited"
  | "internal_error"
  // Client-side only: the request never reached the backend's error envelope.
  | "network_error";

export interface ApiErrorBody {
  code: ErrorCode;
  message: string;
  request_id: string | null;
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody;
}
