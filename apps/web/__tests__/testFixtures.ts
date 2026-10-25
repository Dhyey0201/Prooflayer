import type { CertificateState } from "@/lib/api/useCertificate";
import type {
  Certificate,
  CertificateCheck,
  CertificateClaim,
  CertificateManifest,
} from "@/lib/api/types";

export const RUN_ID = "11111111-1111-1111-1111-111111111111";

export function buildCheck(overrides: Partial<CertificateCheck> = {}): CertificateCheck {
  return {
    requirement_id: "pytest-full-suite",
    kind: "pytest",
    outcome: "PASS",
    reason: "all_tests_passed",
    command_template_id: "pytest-full-suite@0.1.0",
    exit_code: 0,
    output_sha256: "e".repeat(64),
    output_bytes: 120,
    duration_ms: 1500,
    evidence_ref: "e".repeat(64),
    measurements: {},
    ...overrides,
  };
}

export function buildClaim(overrides: Partial<CertificateClaim> = {}): CertificateClaim {
  return {
    claim_id: "agent-final-claim",
    source: "agent",
    trusted: false,
    statement_sha256: "deadbeef".repeat(8),
    statement_chars: 42,
    asserts_tests_passed: true,
    requirement_id: "pytest-full-suite",
    status: "SUPPORTED",
    ...overrides,
  };
}

export function buildManifest(overrides: Partial<CertificateManifest> = {}): CertificateManifest {
  return {
    schema_version: "0.1.0",
    run_id: RUN_ID,
    template_id: "success-validation",
    policy_version: "0.1.0",
    repo_sha: "a".repeat(64),
    checks_version: "0.1.0",
    required_checks: ["pytest-full-suite"],
    verdict: "VERIFIED",
    content_sha256: "c".repeat(64),
    events_through_seq: 20,
    event_chain_head: "h".repeat(64),
    event_chain_valid: true,
    agent: {
      model_id: "prooflayer/scripted-fixture-agent-0.1",
      outcome: "completed",
      sandbox_driver: "mock",
      sandbox_enforced: false,
      policy_sha256: "p".repeat(64),
      worktree_digest: "w".repeat(64),
    },
    verifier: {
      driver: "docker",
      isolation: "container",
      network: "none",
      image: "prooflayer-verifier:0.1.0",
      image_id: "sha256:" + "f".repeat(64),
    },
    artifacts: [{ type: "agent_workspace", sha256: "d".repeat(64) }],
    issued_at: "2026-10-25T00:00:00Z",
    ...overrides,
  };
}

export function buildCertificate(overrides: Partial<Certificate> = {}): Certificate {
  return {
    schema_version: "0.1.0",
    run_id: RUN_ID,
    template_id: "success-validation",
    verdict: "VERIFIED",
    claims: [buildClaim()],
    checks: [buildCheck()],
    evidence_manifest_sha256: "m".repeat(64),
    manifest: buildManifest(),
    limitations: ["The verdict covers only these enumerated requirements: pytest-full-suite."],
    ...overrides,
  };
}

export function readyCertificateState(
  overrides: Partial<Certificate> = {},
  certificateSha256: string | null = "s".repeat(64),
): CertificateState {
  return { phase: "ready", data: buildCertificate(overrides), certificateSha256 };
}
