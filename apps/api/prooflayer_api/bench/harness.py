"""Runs every seeded case through the production run path and records outcomes.

Per case: a fixture run is created through the run service, executed by the
real ``RunOrchestrator`` (bounded agent loop, sandbox driver, snapshot,
independent ``RunVerifier``, certificate, detached ledger) with the case's
fixed model script, then optionally challenged through ``ChallengeProcessor``.
Nothing here decides a verdict: results are read back from the database the
same way the API serves them, then compared with the case's ground truth.

Each pass uses a fresh scratch database and ledger; passes are compared by an
outcome digest that excludes timings, IDs and hashes (which carry timestamps).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from ..ai.client import CircuitBreaker
from ..ai.scripted import ScriptedChallengeTransport, ScriptedTransport
from ..config import Settings
from ..db.models import Base, Certificate, Challenge
from ..db.session import make_engine, make_session_factory
from ..enums import RunMode
from ..evidence.artifacts import list_artifacts, read_artifact
from ..evidence.events import event_to_wire, list_events
from ..evidence.hashchain import canonical_json, sha256_hex
from ..evidence.ledger import EvidenceLedger
from ..evidence.verify_cli import verify_certificate
from ..sandbox.base import SandboxDriver
from ..sandbox.mock import MockSandboxDriver
from ..services import runs as run_service
from ..services.challenges import ChallengeNotAllowedError, ChallengeProcessor, request_challenge
from ..services.fixtures import get_fixture, seed_templates
from ..services.orchestrator import RunOrchestrator
from ..services.runtime import Runtime
from ..verifier.base import VerifierDriver
from .cases import BenchmarkCase
from .faults import FaultInjectingDriver
from .mutations import MUTATIONS, mutated

FLAGGING_CHECKS = {
    "diff-within-allowlist": "diff_outside_allowlist",
    "no-forbidden-access-attempts": "forbidden_access_check_failed",
}


@dataclass
class CaseResult:
    case_id: str
    template: str
    threat: str
    run_status: str
    verdict: str | None
    expected_verdict: str
    sandbox_enforced: bool
    claim_status: str | None
    expected_claim: str | None
    false_claim: bool
    policy_violation: bool
    # Evidence signals that flag a policy violation, e.g. "policy_denied".
    signals: list[str]
    checks: list[dict[str, Any]]
    chain_valid_at_issue: bool | None
    expect_chain_valid: bool
    challenge: dict[str, Any] | None
    agent_ms: float | None
    verification_ms: float | None
    model: dict[str, Any]
    benign_ops: int
    benign_blocked: int
    # Unmodified certificate verified against events + detached ledger.
    certificate_valid: bool | None
    integrity: list[dict[str, Any]] = field(default_factory=list)
    artifacts_checked: int = 0
    artifacts_intact: int = 0

    @property
    def verdict_correct(self) -> bool:
        return self.verdict == self.expected_verdict

    @property
    def claim_correct(self) -> bool:
        return self.claim_status == self.expected_claim

    @property
    def flagged(self) -> bool:
        return bool(self.signals)

    @property
    def challenge_correct(self) -> bool:
        if self.challenge is None:
            return True
        c = self.challenge
        executed_ok = not (c["malicious"] and c["executed"])
        return (
            c["status"] == c["expected_status"]
            and c["outcome"] == c["expected_outcome"]
            and executed_ok
        )

    @property
    def chain_correct(self) -> bool:
        return self.chain_valid_at_issue is None or (
            self.chain_valid_at_issue == self.expect_chain_valid
        )

    @property
    def matches_expectation(self) -> bool:
        return (
            self.verdict_correct
            and self.claim_correct
            and self.challenge_correct
            and self.chain_correct
            and self.artifacts_intact == self.artifacts_checked
            and self.certificate_valid in (None, self.expect_chain_valid)
        )

    def outcome_key(self) -> dict[str, Any]:
        """Everything a deterministic rerun must reproduce exactly."""
        challenge = None
        if self.challenge is not None:
            challenge = {k: self.challenge[k] for k in ("status", "outcome", "reason", "executed")}
        return {
            "case_id": self.case_id,
            "run_status": self.run_status,
            "verdict": self.verdict,
            "claim_status": self.claim_status,
            "signals": self.signals,
            "checks": self.checks,
            "chain_valid_at_issue": self.chain_valid_at_issue,
            "challenge": challenge,
            "benign_ops": self.benign_ops,
            "benign_blocked": self.benign_blocked,
            "model_proposals": self.model["proposals"],
            "model_invalid_proposals": self.model["invalid_proposals"],
            "integrity": [(i["mutation"], i["detected"]) for i in self.integrity],
        }

    def to_wire(self) -> dict[str, Any]:
        data = asdict(self)
        data["verdict_correct"] = self.verdict_correct
        data["claim_correct"] = self.claim_correct
        data["flagged"] = self.flagged
        data["matches_expectation"] = self.matches_expectation
        return data


class _CountingVerifier:
    """Counts container executions so a rejected challenge provably ran nothing."""

    def __init__(self, inner: VerifierDriver) -> None:
        self._inner = inner
        self.name = inner.name
        self.executions = 0

    def probe(self):
        return self._inner.probe()

    def identity(self):
        return self._inner.identity()

    def run_pytest(self, files, targets, timeout_seconds):
        self.executions += 1
        return self._inner.run_pytest(files, targets, timeout_seconds)


def _ms_between(events: Sequence[dict], start: str, end: str) -> float | None:
    times = {}
    for event in events:
        if event["event_type"] in (start, end) and event["event_type"] not in times:
            times[event["event_type"]] = datetime.fromisoformat(event["timestamp"])
    if start not in times or end not in times:
        return None
    return round((times[end] - times[start]).total_seconds() * 1000, 3)


def _model_usage(events: Sequence[dict]) -> dict[str, Any]:
    calls = [e["safe_payload"] for e in events if e["event_type"] == "model.called"]
    proposals = [e["safe_payload"] for e in events if e["event_type"] == "agent.action_proposed"]
    outcomes: dict[str, int] = {}
    for call in calls:
        outcomes[call["outcome"]] = outcomes.get(call["outcome"], 0) + 1
    finished = next(
        (e["safe_payload"] for e in events if e["event_type"] == "agent.finished"), None
    )
    return {
        "calls": len(calls),
        "providers": sorted({c["provider"] for c in calls}),
        "prompt_tokens": sum(c["prompt_tokens"] or 0 for c in calls),
        "completion_tokens": sum(c["completion_tokens"] or 0 for c in calls),
        "latency_ms": sum(c["latency_ms"] or 0 for c in calls),
        "outcomes": dict(sorted(outcomes.items())),
        "proposals": len(proposals),
        "invalid_proposals": sum(not p["valid"] for p in proposals),
        "agent_outcome": finished["outcome"] if finished else None,
    }


def _benign_ops(events: Sequence[dict], case: BenchmarkCase) -> tuple[int, int]:
    """Tool calls the policy permits, and how many of those were blocked anyway."""
    fixture = get_fixture(case.template)
    total = blocked = 0
    for event in events:
        if event["event_type"] != "tool.result":
            continue
        payload = event["safe_payload"]
        action, target = payload["action"], payload["target"]
        permitted = (
            action in ("list_files", "run_check")
            or (action == "read_file" and target not in fixture.read_denied_paths)
            or (action == "write_file" and target in fixture.allowed_paths)
        )
        if permitted:
            total += 1
            blocked += payload["outcome"] == "denied"
    return total, blocked


def _signals(events: Sequence[dict], cert: dict | None, challenge: dict | None) -> list[str]:
    signals = set()
    for event in events:
        payload = event["safe_payload"]
        if event["event_type"] == "policy.denied":
            signals.add("policy_denied")
        elif (
            event["event_type"] == "agent.action_proposed"
            and not payload["valid"]
            and payload["reason"] == "schema_violation"
        ):
            signals.add("action_rejected")
    for check in (cert or {}).get("checks", []):
        if check["outcome"] == "FAIL" and check["requirement_id"] in FLAGGING_CHECKS:
            signals.add(FLAGGING_CHECKS[check["requirement_id"]])
    if challenge is not None and challenge["status"] == "rejected":
        signals.add("challenge_rejected")
    return sorted(signals)


class BenchmarkHarness:
    def __init__(
        self,
        settings: Settings,
        verifier: VerifierDriver,
        workdir: Path,
        *,
        sandbox_factory: Callable[[], SandboxDriver] = MockSandboxDriver,
    ) -> None:
        self._settings = settings
        self._verifier = verifier
        self._workdir = workdir
        self._sandbox_factory = sandbox_factory
        # (label, bytes) of every stored record, for the secret scan.
        self.evidence: list[tuple[str, bytes]] = []

    def run_pass(self, index: int, cases: Sequence[BenchmarkCase]) -> list[CaseResult]:
        engine = make_engine(f"sqlite:///{self._workdir / f'pass-{index}.db'}")
        try:
            # Same schema as `alembic upgrade head` (CI runs `alembic check`).
            Base.metadata.create_all(engine)
            factory = make_session_factory(engine)
            with factory.begin() as session:
                seed_templates(session)
            ledger = EvidenceLedger(self._workdir / f"pass-{index}-ledger.jsonl")
            driver = self._sandbox_factory()
            results = [self._run_case(factory, ledger, driver, case) for case in cases]
            if ledger.path is not None and ledger.path.exists():
                self.evidence.append((f"pass-{index}:ledger", ledger.path.read_bytes()))
            return results
        finally:
            engine.dispose()

    def _runtime(
        self,
        case: BenchmarkCase,
        driver: SandboxDriver,
        verifier: _CountingVerifier,
        ledger: EvidenceLedger,
    ) -> Runtime:
        challenge_factory = None
        if case.challenge is not None:
            proposal = json.dumps(case.challenge.proposal)
            challenge_factory = lambda run: ScriptedChallengeTransport(  # noqa: E731
                case.template, script=[proposal]
            )
        return Runtime(
            settings=self._settings,
            driver=driver,
            transport_factory=lambda run: ScriptedTransport(case.template, script=case.script),
            verifier=verifier,
            challenge_transport_factory=challenge_factory,
            ledger=ledger,
            breaker=CircuitBreaker(),
            sleep=lambda _seconds: None,
        )

    def _run_case(
        self,
        factory: sessionmaker,
        ledger: EvidenceLedger,
        base_driver: SandboxDriver,
        case: BenchmarkCase,
    ) -> CaseResult:
        driver = (
            FaultInjectingDriver(base_driver, case.fault, factory) if case.fault else base_driver
        )
        verifier = _CountingVerifier(self._verifier)
        runtime = self._runtime(case, driver, verifier, ledger)
        with factory() as session:
            run_id = run_service.create_run(
                session, template_id=case.template, mode=RunMode.FIXTURE, max_pending_runs=100
            ).run.id
        RunOrchestrator(factory, runtime).process(run_id)
        challenge = self._challenge(factory, runtime, verifier, case, run_id)

        with factory() as session:
            run = run_service.get_run(session, run_id)
            row = session.scalar(select(Certificate).where(Certificate.run_id == run_id))
            cert = row.body_json if row is not None else None
            events = [event_to_wire(e) for e in list_events(session, run_id, limit=10_000)]
            artifacts = list_artifacts(session, run_id)
            intact = 0
            for artifact in artifacts:
                try:
                    data = read_artifact(artifact)
                except Exception:  # noqa: S112 - counted as not intact
                    continue
                intact += 1
                self.evidence.append((f"{case.id}:artifact:{artifact.type}", data))
            status, verdict = run.status, run.verdict
            claim_text = run.agent_claim

        self.evidence.append((f"{case.id}:events", canonical_json(events)))
        if cert is not None:
            self.evidence.append((f"{case.id}:certificate", canonical_json(cert)))
        if claim_text:
            self.evidence.append((f"{case.id}:claim", claim_text.encode()))

        enforced = bool(cert and cert["manifest"]["agent"]["sandbox_enforced"])
        claims = (cert or {}).get("claims", [])
        benign, blocked = _benign_ops(events, case)
        result = CaseResult(
            case_id=case.id,
            template=case.template.value,
            threat=case.threat.value,
            run_status=str(status),
            verdict=str(verdict) if verdict else None,
            expected_verdict=case.expected_for(enforced).value,
            sandbox_enforced=enforced,
            claim_status=claims[0]["status"] if claims else None,
            expected_claim=case.expected_claim,
            false_claim=case.false_claim,
            policy_violation=case.policy_violation,
            signals=_signals(events, cert, challenge),
            checks=[
                {k: c[k] for k in ("requirement_id", "outcome", "reason")}
                for c in (cert or {}).get("checks", [])
            ],
            chain_valid_at_issue=cert["manifest"]["event_chain_valid"] if cert else None,
            expect_chain_valid=case.expect_chain_valid,
            challenge=challenge,
            agent_ms=_ms_between(events, "sandbox.provisioned", "agent.finished"),
            verification_ms=_ms_between(events, "agent.finished", "certificate.issued"),
            model=_model_usage(events),
            benign_ops=benign,
            benign_blocked=blocked,
            certificate_valid=None,
            artifacts_checked=len(artifacts),
            artifacts_intact=intact,
        )
        if cert is not None:
            self._integrity(result, cert, events, ledger)
        return result

    def _challenge(
        self,
        factory: sessionmaker,
        runtime: Runtime,
        verifier: _CountingVerifier,
        case: BenchmarkCase,
        run_id: str,
    ) -> dict[str, Any] | None:
        seed = case.challenge
        if seed is None:
            return None
        before = verifier.executions
        try:
            with factory() as session:
                challenge_id = request_challenge(
                    session, run_id, max_per_run=self._settings.max_challenges_per_run
                ).id
        except ChallengeNotAllowedError as exc:
            status, outcome, reason = "not_allowed", None, exc.reason
        else:
            ChallengeProcessor(factory, runtime).process(challenge_id)
            with factory() as session:
                row = session.get(Challenge, challenge_id)
                status, reason = str(row.status), row.reason
                outcome = str(row.outcome) if row.outcome else None
        return {
            "status": status,
            "outcome": outcome,
            "reason": reason,
            "executed": verifier.executions > before,
            "expected_status": seed.expected_status,
            "expected_outcome": seed.expected_outcome,
            "malicious": seed.malicious,
            "test_sha256": sha256_hex(seed.proposal["test_source"].encode()),
        }

    def _integrity(
        self, result: CaseResult, cert: dict, events: list[dict], ledger: EvidenceLedger
    ) -> None:
        result.certificate_valid = verify_certificate(cert, events, ledger=ledger)["valid"]
        if not result.certificate_valid:
            # Already invalid (e.g. corrupted before issue): mutations prove nothing more.
            return
        for name in MUTATIONS:
            m_cert, m_events = mutated(name, cert, events)
            with_ledger = verify_certificate(m_cert, m_events, ledger=ledger)
            alone = verify_certificate(m_cert, m_events)
            result.integrity.append(
                {
                    "mutation": name,
                    "detected": not with_ledger["valid"],
                    "detected_without_ledger": not alone["valid"],
                    "failed_checks": sorted(
                        k for k, v in with_ledger["checks"].items() if not v["ok"]
                    ),
                }
            )


def outcome_digest(results: Sequence[CaseResult]) -> str:
    return sha256_hex(canonical_json([r.outcome_key() for r in results]))
