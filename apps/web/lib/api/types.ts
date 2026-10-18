/**
 * Types mirror `contracts/openapi.yaml` and the backend enums in
 * `apps/api/prooflayer_api/enums.py`. Keep both in sync when the contract
 * changes; this file never defines new wire shapes on its own.
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

export interface Run {
  id: string;
  template_id: string;
  status: RunStatus;
  mode: RunMode;
  created_at: string;
  updated_at?: string;
  agent_claim?: string | null;
  verdict?: Verdict;
}

export type ErrorCode =
  | "bad_request"
  | "validation_error"
  | "not_found"
  | "method_not_allowed"
  | "conflict"
  | "rate_limited"
  | "internal_error"
  | "network_error";

export interface ApiErrorBody {
  code: ErrorCode;
  message: string;
  request_id: string | null;
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody;
}
