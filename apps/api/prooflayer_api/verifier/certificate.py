"""Evidence certificates (schema 0.1.0) and their manifest.

The certificate is assembled only from verifier measurements and recorded
events. The agent's claim appears as an *untrusted input* whose status is
derived from the measured checks; it never sets the verdict.

``manifest`` binds the certificate to its evidence: the event chain head at
issue time, a digest of the verdict/claims/checks/limitations, the agent and
verifier runtime identities and every artifact digest. ``evidence_manifest_sha256``
is the SHA-256 of the manifest's canonical JSON and is also written to the
detached ledger, so ``python -m prooflayer_api.evidence.verify_cli`` can check
all of it offline. No signing key is involved: this is tamper evidence, not
non-repudiation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..enums import CheckOutcome, Verdict
from ..evidence.hashchain import canonical_json, sha256_hex
from ..services.fixtures import FixtureTemplate
from .base import RuntimeIdentity
from .checks import CHECKS_VERSION, CheckResult

SCHEMA_VERSION = "0.1.0"
CLAIM_REQUIREMENT = "pytest-full-suite"


@dataclass(frozen=True)
class AgentContext:
    claim_text: str | None
    claim_tests_passed: bool | None
    model_id: str | None
    sandbox_driver: str | None
    sandbox_enforced: bool
    policy_sha256: str | None
    worktree_digest: str | None
    agent_outcome: str


def check_to_wire(result: CheckResult) -> dict[str, Any]:
    return {
        "requirement_id": result.requirement_id,
        "kind": result.kind.value,
        "outcome": result.outcome.value,
        "reason": result.reason,
        "command_template_id": result.command_template_id,
        "exit_code": result.exit_code,
        "output_sha256": result.output_sha256,
        "output_bytes": result.output_bytes,
        "duration_ms": result.duration_ms,
        "evidence_ref": result.evidence_ref,
        "measurements": dict(result.measurements),
    }


def claim_status(tests_passed: bool | None, results: Sequence[CheckResult]) -> str:
    """SUPPORTED / CONTRADICTED by the measured suite, else UNVERIFIED."""
    measured = next((r for r in results if r.requirement_id == CLAIM_REQUIREMENT), None)
    if tests_passed is None or measured is None or measured.outcome is CheckOutcome.INCONCLUSIVE:
        return "UNVERIFIED"
    return (
        "SUPPORTED" if (measured.outcome is CheckOutcome.PASS) == tests_passed else "CONTRADICTED"
    )


def build_claims(agent: AgentContext, results: Sequence[CheckResult]) -> list[dict[str, Any]]:
    if agent.claim_text is None:
        return []
    return [
        {
            "claim_id": "agent-final-claim",
            "source": "agent",
            "trusted": False,
            "statement_sha256": sha256_hex(agent.claim_text.encode()),
            "statement_chars": len(agent.claim_text),
            "asserts_tests_passed": agent.claim_tests_passed,
            "requirement_id": CLAIM_REQUIREMENT,
            "status": claim_status(agent.claim_tests_passed, results),
        }
    ]


def build_limitations(
    fixture: FixtureTemplate, agent: AgentContext, verifier: RuntimeIdentity | None
) -> list[str]:
    limits = [
        "The verdict covers only these enumerated requirements: "
        + ", ".join(fixture.required_checks)
        + ".",
        "PASS means the pinned check passed in the recorded verifier image; "
        "it does not establish behaviour the checks do not exercise.",
        "The agent's claim is untrusted input: it is compared with measurements, never one itself.",
        "The event chain and manifest provide tamper evidence, not tamper prevention; "
        "nothing is signed, so this certificate is not non-repudiable.",
        "Proof challenges run after issue are reported separately and do not change this verdict.",
    ]
    if not agent.sandbox_enforced:
        limits.append(
            "The agent ran in the mock sandbox: no policy was enforced by a runtime and the "
            "agent's own checks were simulated. Policy denials are modelled, not enforced."
        )
    if verifier is None:
        limits.append(
            "No independent verifier runtime was available; executed checks are INCONCLUSIVE."
        )
    elif verifier.isolation == "container":
        limits.append(
            "The independent verifier is a network-less Docker container (container isolation), "
            "not an OpenShell-enforced sandbox."
        )
    if agent.agent_outcome != "completed":
        limits.append(f"The agent did not complete (outcome: {agent.agent_outcome}).")
    return limits


def build_certificate(
    *,
    run_id: str,
    fixture: FixtureTemplate,
    verdict: Verdict,
    results: Sequence[CheckResult],
    agent: AgentContext,
    verifier: RuntimeIdentity | None,
    events_through_seq: int,
    event_chain_head: str,
    chain_valid: bool,
    artifacts: Sequence[dict[str, Any]],
    issued_at: str,
) -> dict[str, Any]:
    claims = build_claims(agent, results)
    checks = [check_to_wire(r) for r in results]
    limitations = build_limitations(fixture, agent, verifier)
    content = {
        "verdict": verdict.value,
        "claims": claims,
        "checks": checks,
        "limitations": limitations,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "template_id": fixture.id.value,
        "policy_version": fixture.policy_version,
        "repo_sha": fixture.repo_sha,
        "checks_version": CHECKS_VERSION,
        "required_checks": list(fixture.required_checks),
        "verdict": verdict.value,
        "content_sha256": sha256_hex(canonical_json(content)),
        "events_through_seq": events_through_seq,
        "event_chain_head": event_chain_head,
        "event_chain_valid": chain_valid,
        "agent": {
            "model_id": agent.model_id,
            "outcome": agent.agent_outcome,
            "sandbox_driver": agent.sandbox_driver,
            "sandbox_enforced": agent.sandbox_enforced,
            "policy_sha256": agent.policy_sha256,
            "worktree_digest": agent.worktree_digest,
        },
        "verifier": None
        if verifier is None
        else {
            "driver": verifier.driver,
            "isolation": verifier.isolation,
            "network": verifier.network,
            "image": verifier.image,
            "image_id": verifier.image_id,
        },
        "artifacts": sorted(artifacts, key=lambda a: (a["type"], a["sha256"])),
        "issued_at": issued_at,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "template_id": fixture.id.value,
        "verdict": verdict.value,
        "claims": claims,
        "checks": checks,
        "limitations": limitations,
        "evidence_manifest_sha256": manifest_digest(manifest),
        "manifest": manifest,
    }


def manifest_digest(manifest: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(manifest))


def certificate_digest(certificate: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(certificate))


def content_digest(certificate: dict[str, Any]) -> str:
    return sha256_hex(
        canonical_json({k: certificate[k] for k in ("verdict", "claims", "checks", "limitations")})
    )
