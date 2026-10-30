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
  /** Live-model runs may use the unenforced mock sandbox (opt-in development fallback). */
  unenforced_live_allowed: boolean;
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

export type EventType =
  | "run.created"
  | "run.status_changed"
  | "sandbox.provisioned"
  | "sandbox.released"
  | "model.called"
  | "agent.action_proposed"
  | "tool.result"
  | "policy.denied"
  | "agent.claimed"
  | "agent.finished"
  | "workspace.snapshot"
  | "check.completed"
  | "certificate.issued"
  | "challenge.requested"
  | "challenge.proposed"
  | "challenge.rejected"
  | "challenge.completed";

export type EventActor = "api" | "orchestrator" | "seeder" | "verifier";

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
  | "payload_too_large"
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

/** Mirrors `enums.CheckOutcome`; produced by the independent verifier. */
export type CheckOutcome = "PASS" | "FAIL" | "INCONCLUSIVE";

/** A claim's status is derived from the measured check, never from the claim itself. */
export type ClaimStatus = "SUPPORTED" | "CONTRADICTED" | "UNVERIFIED";

export interface CertificateCheck {
  requirement_id: string;
  kind: "pytest" | "diff_allowlist" | "policy_attempts";
  outcome: CheckOutcome;
  reason: string | null;
  command_template_id: string | null;
  exit_code: number | null;
  output_sha256: string | null;
  output_bytes: number | null;
  duration_ms: number | null;
  evidence_ref: string | null;
  /** Small scalar counts/flags; shape varies by check kind — render generically. */
  measurements: Record<string, string | number | boolean | null>;
}

export interface CertificateClaim {
  claim_id: string;
  source: "agent";
  trusted: false;
  statement_sha256: string;
  statement_chars: number;
  asserts_tests_passed: boolean | null;
  requirement_id: string;
  status: ClaimStatus;
}

export interface CertificateManifestAgent {
  model_id: string | null;
  outcome: string;
  sandbox_driver: string | null;
  sandbox_enforced: boolean;
  policy_sha256: string | null;
  worktree_digest: string | null;
}

export interface CertificateManifestVerifier {
  driver: string;
  isolation: string;
  network: string;
  image: string;
  image_id: string;
}

export interface CertificateArtifact {
  type: string;
  sha256: string;
  [key: string]: unknown;
}

export interface CertificateManifest {
  schema_version: string;
  run_id: string;
  template_id: string;
  policy_version: string;
  repo_sha: string;
  checks_version: string;
  required_checks: string[];
  verdict: Exclude<Verdict, null>;
  content_sha256: string;
  events_through_seq: number;
  event_chain_head: string;
  event_chain_valid: boolean;
  agent: CertificateManifestAgent;
  verifier: CertificateManifestVerifier | null;
  artifacts: CertificateArtifact[];
  issued_at: string;
}

export interface Certificate {
  schema_version: string;
  run_id: string;
  template_id: string;
  verdict: Exclude<Verdict, null>;
  claims: CertificateClaim[];
  checks: CertificateCheck[];
  evidence_manifest_sha256: string;
  manifest: CertificateManifest;
  limitations: string[];
}

export type ChallengeStatus = "queued" | "running" | "completed" | "rejected" | "error";

/** The model's proposed test. `test_source` is untrusted — render as code, never HTML. */
export interface Challenge {
  id: string;
  run_id: string;
  status: ChallengeStatus;
  requirement_id: string | null;
  challenge_type: string | null;
  validated: boolean | null;
  outcome: CheckOutcome | null;
  reason: string | null;
  test_sha256: string | null;
  test_bytes: number | null;
  test_count: number | null;
  test_source: string | null;
  exit_code: number | null;
  output_sha256: string | null;
  output_bytes: number | null;
  duration_ms: number | null;
  provider: string | null;
  model_id: string | null;
  verifier_image_id: string | null;
  created_at: string;
  finished_at: string | null;
}

/** Statuses a challenge can still move through; mirrors `challenges.ACTIVE`. */
export const ACTIVE_CHALLENGE_STATUSES: readonly ChallengeStatus[] = ["queued", "running"];

/** One ratio from the benchmark report; `value` is null when `denominator` is 0. */
export interface BenchmarkRatio {
  value: number | null;
  numerator: number;
  denominator: number;
  definition: string;
}

/**
 * `GET /benchmark`: the report `make benchmark` publishes
 * (`benchmarks/results/benchmark-report.json`). Only the fields the
 * benchmark page renders are typed; the rest is passed through untouched.
 */
export interface BenchmarkReport {
  schema_version: string;
  generated_at: string;
  seed_count: number;
  passes: number;
  deterministic: boolean;
  all_expectations_met: boolean;
  mismatched_cases: string[];
  metrics: Record<string, BenchmarkRatio>;
  verification_overhead: {
    samples: number;
    verification_ms_median: number | null;
    verification_ms_p95: number | null;
    definition: string;
  };
  secret_scan: { matches: number; bytes_scanned: number };
  environment: {
    platform: string;
    sandbox: { driver: string; enforced: boolean };
    verifier: { driver: string; isolation: string; network: string; image_id: string | null };
    model: { provider: string; model_id: string };
  };
  limitations: string[];
}
