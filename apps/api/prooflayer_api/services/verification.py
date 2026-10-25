"""Independent verification of a finished agent run and certificate issue.

Runs only in the ``verifying`` state, after the agent's sandbox has been
released. Every required check comes from ``verifier.checks.CHECK_TEMPLATES``:

* pytest checks execute in a fresh verifier container on a tree rebuilt from
  the pinned fixture baseline plus only the agent's allowed files;
* the allowlist check compares the agent sandbox's final state with the baseline;
* the forbidden-access check reads the run's own recorded enforcement events.

The verdict follows ``decide_verdict`` and nothing else; the agent's claim is
only compared against it. Check rows, the certificate, its ``certificate.issued``
event and the final status change are committed in one transaction. The
detached ledger entry is appended after that commit.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import sessionmaker

from ..db.models import Certificate, Check
from ..enums import Actor, EventType, RunStatus, Verdict
from ..evidence.artifacts import put_artifact
from ..evidence.events import append_event, event_to_wire, list_events
from ..evidence.hashchain import canonical_json, format_timestamp, verify_chain
from ..services.fixtures import FixtureTemplate
from ..verifier.base import RuntimeIdentity, VerifierUnavailableError
from ..verifier.certificate import (
    SCHEMA_VERSION,
    AgentContext,
    build_certificate,
    certificate_digest,
)
from ..verifier.checks import (
    CHECK_TEMPLATES,
    CheckKind,
    CheckResult,
    decide_verdict,
    diff_result,
    inconclusive,
    policy_result,
    pytest_result,
)
from ..verifier.snapshot import (
    WorkspaceDiff,
    baseline_files,
    diff_workspace,
    tree_digest,
    verification_tree,
)
from . import runs as run_service
from .runtime import Runtime
from .state_machine import InvalidTransitionError

log = logging.getLogger(__name__)

AGENT_WORKSPACE_ARTIFACT = "agent_workspace"
VERIFIER_OUTPUT_ARTIFACT = "verifier_output"
STATUS_FOR_VERDICT = {
    Verdict.VERIFIED: RunStatus.VERIFIED,
    Verdict.FAILED: RunStatus.FAILED,
    Verdict.INCONCLUSIVE: RunStatus.INCONCLUSIVE,
}


@dataclass(frozen=True)
class AgentRunState:
    """What the orchestrator measured about the agent run, passed to verification."""

    agent_outcome: str
    claim_text: str | None
    claim_tests_passed: bool | None
    model_id: str | None
    sandbox_driver: str
    sandbox_enforced: bool
    policy_sha256: str
    # Final bytes of each baseline/allowed path in the agent sandbox; None if unavailable.
    observed: Mapping[str, bytes | None] | None


def encode_agent_files(files: Mapping[str, bytes | None]) -> bytes:
    return canonical_json(
        {p: None if d is None else base64.b64encode(d).decode() for p, d in files.items()}
    )


def decode_agent_files(data: bytes) -> dict[str, bytes | None]:
    return {p: None if d is None else base64.b64decode(d) for p, d in json.loads(data).items()}


class RunVerifier:
    def __init__(self, session_factory: sessionmaker, runtime: Runtime) -> None:
        self._factory = session_factory
        self._runtime = runtime

    def _event(self, run_id: str, event_type: EventType, payload: dict[str, Any]) -> None:
        with self._factory.begin() as session:
            append_event(session, run_id, event_type, Actor.VERIFIER, payload)

    def _artifact(self, run_id: str, kind: str, data: bytes) -> str:
        with self._factory.begin() as session:
            return put_artifact(session, run_id, kind, data).content_sha256

    # -- checks --------------------------------------------------------------

    def _identity(self) -> tuple[RuntimeIdentity | None, str | None]:
        try:
            return self._runtime.verifier.identity(), None
        except VerifierUnavailableError as exc:
            return None, exc.reason

    def _run_pytest(
        self,
        run_id: str,
        fixture: FixtureTemplate,
        targets: tuple[str, ...],
        tree: dict[str, bytes],
    ):
        execution = self._runtime.verifier.run_pytest(
            tree, targets, self._runtime.settings.verifier_timeout_seconds
        )
        ref = self._artifact(run_id, VERIFIER_OUTPUT_ARTIFACT, execution.excerpt)
        return execution, ref

    def _check(
        self,
        run_id: str,
        fixture: FixtureTemplate,
        requirement_id: str,
        state: AgentRunState,
        diff: WorkspaceDiff | None,
        identity: RuntimeIdentity | None,
        unavailable_reason: str | None,
        pinned: bool,
    ) -> CheckResult:
        template = CHECK_TEMPLATES[requirement_id]
        if not pinned:
            return inconclusive(template, "fixture_digest_mismatch")
        if template.kind is CheckKind.DIFF_ALLOWLIST:
            return diff_result(template, diff)
        if template.kind is CheckKind.POLICY_ATTEMPTS:
            with self._factory() as session:
                events = [event_to_wire(e) for e in list_events(session, run_id)]
            return policy_result(
                template, events, fixture.read_denied_paths, state.sandbox_enforced
            )
        # PYTEST
        if state.agent_outcome != "completed":
            return inconclusive(template, "agent_did_not_complete")
        if state.observed is None:
            return inconclusive(template, "snapshot_unavailable")
        if any(p not in state.observed for p in fixture.allowed_paths):
            return inconclusive(template, "snapshot_incomplete")
        if identity is None:
            return inconclusive(template, unavailable_reason or "verifier_unavailable")
        tree = verification_tree(baseline_files(fixture.id), state.observed, fixture.allowed_paths)
        try:
            execution, ref = self._run_pytest(run_id, fixture, template.pytest_targets, tree)
        except VerifierUnavailableError as exc:
            return inconclusive(template, exc.reason)
        return pytest_result(template, execution, ref)

    def _record_check(
        self, run_id: str, result: CheckResult, identity: RuntimeIdentity | None
    ) -> None:
        executed = result.kind is CheckKind.PYTEST and result.exit_code is not None
        self._event(
            run_id,
            EventType.CHECK_COMPLETED,
            {
                "requirement_id": result.requirement_id,
                "kind": result.kind.value,
                "outcome": result.outcome.value,
                "reason": result.reason[:200],
                "command_template_id": result.command_template_id,
                "exit_code": result.exit_code,
                "output_sha256": result.output_sha256,
                "output_bytes": result.output_bytes,
                "duration_ms": result.duration_ms,
                "evidence_ref": result.evidence_ref,
                "driver": identity.driver if identity and executed else None,
                "isolation": identity.isolation if identity and executed else None,
                "network": identity.network if identity and executed else None,
                "image_id": identity.image_id if identity and executed else None,
            },
        )

    # -- entry point ---------------------------------------------------------

    def verify(self, run_id: str, fixture: FixtureTemplate, state: AgentRunState) -> None:
        baseline = baseline_files(fixture.id)
        pinned = tree_digest(baseline) == fixture.repo_sha
        diff = None
        worktree = None
        artifacts: list[dict[str, Any]] = []
        if state.observed is not None:
            diff = diff_workspace(baseline, state.observed, fixture.allowed_paths)
            worktree = tree_digest(state.observed)
            allowed = {p: state.observed.get(p) for p in fixture.allowed_paths}
            ref = self._artifact(run_id, AGENT_WORKSPACE_ARTIFACT, encode_agent_files(allowed))
            artifacts.append(
                {"type": AGENT_WORKSPACE_ARTIFACT, "sha256": ref, "role": "agent_output"}
            )
            self._event(
                run_id,
                EventType.WORKSPACE_SNAPSHOT,
                {
                    "worktree_digest": worktree,
                    "baseline_digest": tree_digest(baseline),
                    "files_observed": len(state.observed),
                    "changed_files": len(diff.changed),
                    "outside_allowlist": len(diff.outside_allowlist),
                    "unreadable_files": len(diff.unreadable),
                    "complete": diff.complete,
                },
            )

        identity, unavailable = self._identity()
        results = []
        for requirement_id in fixture.required_checks:
            result = self._check(
                run_id, fixture, requirement_id, state, diff, identity, unavailable, pinned
            )
            self._record_check(run_id, result, identity)
            if result.evidence_ref:
                artifacts.append(
                    {
                        "type": VERIFIER_OUTPUT_ARTIFACT,
                        "sha256": result.evidence_ref,
                        "role": result.requirement_id,
                    }
                )
            results.append(result)

        self._issue(run_id, fixture, state, results, identity, worktree, artifacts)

    def _issue(
        self,
        run_id: str,
        fixture: FixtureTemplate,
        state: AgentRunState,
        results: list[CheckResult],
        identity: RuntimeIdentity | None,
        worktree: str | None,
        artifacts: list[dict[str, Any]],
    ) -> None:
        session = self._factory()
        try:
            events = [event_to_wire(e) for e in list_events(session, run_id)]
            chain = verify_chain(events)
            verdict = decide_verdict(results, chain.valid)
            certificate = build_certificate(
                run_id=run_id,
                fixture=fixture,
                verdict=verdict,
                results=results,
                agent=AgentContext(
                    claim_text=state.claim_text,
                    claim_tests_passed=state.claim_tests_passed,
                    model_id=state.model_id,
                    sandbox_driver=state.sandbox_driver,
                    sandbox_enforced=state.sandbox_enforced,
                    policy_sha256=state.policy_sha256,
                    worktree_digest=worktree,
                    agent_outcome=state.agent_outcome,
                ),
                verifier=identity,
                events_through_seq=events[-1]["seq"],
                event_chain_head=events[-1]["event_hash"],
                chain_valid=chain.valid,
                artifacts=artifacts,
                issued_at=format_timestamp(datetime.now(UTC)),
            )
            cert_sha = certificate_digest(certificate)
            manifest_sha = certificate["evidence_manifest_sha256"]
            run = run_service.get_run(session, run_id)
            if worktree is not None:
                run.worktree_digest = worktree
            for result in results:
                session.add(
                    Check(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        requirement_id=result.requirement_id,
                        kind=result.kind.value,
                        outcome=result.outcome,
                        evidence_ref=result.evidence_ref,
                        command_template_id=result.command_template_id,
                        exit_code=result.exit_code,
                        reason=result.reason[:64],
                        output_sha256=result.output_sha256,
                        duration_ms=result.duration_ms,
                        measurements_json=dict(result.measurements),
                    )
                )
            session.add(
                Certificate(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    schema_version=SCHEMA_VERSION,
                    verdict=verdict,
                    json_sha256=cert_sha,
                    manifest_sha256=manifest_sha,
                    body_json=certificate,
                )
            )
            session.flush()
            append_event(
                session,
                run_id,
                EventType.CERTIFICATE_ISSUED,
                Actor.VERIFIER,
                {
                    "schema_version": SCHEMA_VERSION,
                    "verdict": verdict.value,
                    "certificate_sha256": cert_sha,
                    "manifest_sha256": manifest_sha,
                    "events_through_seq": events[-1]["seq"],
                },
            )
            run_service.apply_transition(
                session,
                run,
                STATUS_FOR_VERDICT[verdict],
                reason="independent_verification",
                actor=Actor.VERIFIER,
            )
            session.commit()
        except (InvalidTransitionError, run_service.ConcurrentUpdateError):
            # Canceled while verifying: nothing is issued.
            session.rollback()
            return
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        try:
            self._runtime.ledger.append(
                {
                    "run_id": run_id,
                    "certificate_sha256": cert_sha,
                    "manifest_sha256": manifest_sha,
                    "verdict": verdict.value,
                    "issued_at": certificate["manifest"]["issued_at"],
                }
            )
        except OSError:
            # The certificate stands; the CLI will report the missing ledger entry.
            log.exception("could not append run %s to the evidence ledger", run_id)
