"""Proof challenges for a certified run.

``request_challenge`` (API) queues one; the worker calls ``ChallengeProcessor``,
which asks the model for a test, validates it statically and, only if it
passes validation, runs it in the independent verifier against the run's
recorded workspace (pinned baseline + the agent's allowed files). Outcomes come
from the verifier's exit code; a rejected or unrunnable proposal is never
promoted to a result. A challenge does not change the run's certificate.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from ..ai.client import CallRecord, ModelBudgetExceededError, ModelUnavailableError
from ..db.models import Certificate, Challenge
from ..enums import Actor, ChallengeStatus, CheckOutcome, EventType, RunStatus, TemplateId
from ..evidence.artifacts import latest_artifact, put_artifact, read_artifact
from ..evidence.events import append_event
from ..verifier.base import VerifierUnavailableError
from ..verifier.challenge import (
    CHALLENGE_TEST_PATH,
    ChallengeRejectedError,
    validate_test_source,
)
from ..verifier.checks import pytest_outcome
from ..verifier.proposer import propose_challenge
from ..verifier.snapshot import baseline_files, tree_digest, verification_tree
from . import runs as run_service
from .fixtures import get_fixture
from .runtime import Runtime
from .verification import AGENT_WORKSPACE_ARTIFACT, decode_agent_files

log = logging.getLogger(__name__)

CHALLENGE_TEST_ARTIFACT = "challenge_test"
CHALLENGE_OUTPUT_ARTIFACT = "challenge_output"
CHALLENGEABLE = frozenset({RunStatus.VERIFIED, RunStatus.FAILED, RunStatus.INCONCLUSIVE})
ACTIVE = (ChallengeStatus.QUEUED, ChallengeStatus.RUNNING)


class ChallengeNotAllowedError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ChallengeLimitError(Exception):
    pass


def request_challenge(session: Session, run_id: str, *, max_per_run: int) -> Challenge:
    """Queue a challenge for a certified run. Commits."""
    run = run_service.get_run(session, run_id)
    try:
        if RunStatus(run.status) not in CHALLENGEABLE:
            raise ChallengeNotAllowedError("run_not_certified")
        if session.scalar(select(Certificate.id).where(Certificate.run_id == run_id)) is None:
            raise ChallengeNotAllowedError("no_certificate")
        if latest_artifact(session, run_id, AGENT_WORKSPACE_ARTIFACT) is None:
            raise ChallengeNotAllowedError("no_recorded_workspace")
        if session.scalar(
            select(Challenge.id).where(Challenge.run_id == run_id, Challenge.status.in_(ACTIVE))
        ):
            raise ChallengeNotAllowedError("challenge_in_progress")
        count = session.scalar(
            select(func.count()).select_from(Challenge).where(Challenge.run_id == run_id)
        )
        if count >= max_per_run:
            raise ChallengeLimitError(count)
        challenge = Challenge(id=str(uuid.uuid4()), run_id=run_id, status=ChallengeStatus.QUEUED)
        session.add(challenge)
        session.flush()
        append_event(
            session,
            run_id,
            EventType.CHALLENGE_REQUESTED,
            Actor.API,
            {"challenge_id": challenge.id},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return challenge


def list_challenges(session: Session, run_id: str) -> list[Challenge]:
    return list(
        session.scalars(
            select(Challenge).where(Challenge.run_id == run_id).order_by(Challenge.created_at)
        )
    )


def challenge_test_source(session: Session, challenge: Challenge) -> str | None:
    """The stored (untrusted) test source, re-hashed on read."""
    if challenge.test_sha256 is None:
        return None
    artifact = latest_artifact(
        session, challenge.run_id, CHALLENGE_TEST_ARTIFACT + ":" + challenge.id
    )
    return None if artifact is None else read_artifact(artifact).decode()


def next_queued_challenge_id(session: Session) -> str | None:
    challenge_id = session.scalar(
        select(Challenge.id)
        .where(Challenge.status == ChallengeStatus.QUEUED)
        .order_by(Challenge.created_at)
        .limit(1)
    )
    session.rollback()
    return challenge_id


def recover_interrupted_challenges(session_factory: sessionmaker) -> int:
    with session_factory() as session:
        stuck = list(
            session.scalars(select(Challenge).where(Challenge.status == ChallengeStatus.RUNNING))
        )
        for challenge in stuck:
            challenge.status = ChallengeStatus.ERROR
            challenge.reason = "worker_restarted"
            challenge.finished_at = datetime.now(UTC)
        session.commit()
        return len(stuck)


@dataclass
class _Context:
    challenge_id: str
    run_id: str
    template_id: TemplateId
    claim: str | None


class ChallengeProcessor:
    def __init__(self, session_factory: sessionmaker, runtime: Runtime) -> None:
        self._factory = session_factory
        self._runtime = runtime

    def _event(self, run_id: str, event_type: EventType, payload: dict, actor=Actor.VERIFIER):
        with self._factory.begin() as session:
            append_event(session, run_id, event_type, actor, payload)

    def _claim(self, challenge_id: str) -> _Context | None:
        """queued -> running under the optimistic lock; None if someone else won."""
        session = self._factory()
        try:
            challenge = session.get(Challenge, challenge_id)
            if challenge is None or challenge.status != ChallengeStatus.QUEUED:
                return None
            challenge.status = ChallengeStatus.RUNNING
            run = run_service.get_run(session, challenge.run_id)
            context = _Context(challenge.id, run.id, TemplateId(run.task_id), run.agent_claim)
            session.commit()
            return context
        except StaleDataError:
            session.rollback()
            return None
        finally:
            session.close()

    def _finish(self, challenge_id: str, status: ChallengeStatus, **fields) -> None:
        with self._factory.begin() as session:
            challenge = session.get(Challenge, challenge_id)
            challenge.status = status
            challenge.finished_at = datetime.now(UTC)
            for key, value in fields.items():
                setattr(challenge, key, value)

    def _reject(self, ctx: _Context, reason: str, **fields) -> None:
        self._event(
            ctx.run_id,
            EventType.CHALLENGE_REJECTED,
            {
                "challenge_id": ctx.challenge_id,
                "reason": reason,
                "test_sha256": fields.get("test_sha256"),
            },
        )
        self._finish(
            ctx.challenge_id, ChallengeStatus.REJECTED, validated=False, reason=reason, **fields
        )

    def process(self, challenge_id: str) -> ChallengeStatus | None:
        ctx = self._claim(challenge_id)
        if ctx is None:
            return None
        try:
            self._execute(ctx)
        except Exception:
            log.exception("challenge %s failed", challenge_id)
            self._finish(ctx.challenge_id, ChallengeStatus.ERROR, reason="internal_error")
        with self._factory() as session:
            return ChallengeStatus(session.get(Challenge, challenge_id).status)

    def _execute(self, ctx: _Context) -> None:
        fixture = get_fixture(ctx.template_id)
        with self._factory() as session:
            run = run_service.get_run(session, ctx.run_id)
            artifact = latest_artifact(session, ctx.run_id, AGENT_WORKSPACE_ARTIFACT)
            agent_files = decode_agent_files(read_artifact(artifact))

            def observer(record: CallRecord) -> None:
                self._event(
                    ctx.run_id,
                    EventType.MODEL_CALLED,
                    {
                        "provider": record.provider,
                        "model_id": record.model_id,
                        "attempt": record.attempt,
                        "outcome": record.outcome.value,
                        "prompt_tokens": record.prompt_tokens,
                        "completion_tokens": record.completion_tokens,
                        "latency_ms": record.latency_ms,
                        "error_code": record.error_code,
                    },
                    Actor.ORCHESTRATOR,
                )

            client = self._runtime.challenge_client(run, observer)

        context_files = {
            p: d.decode("utf-8", errors="replace") for p, d in agent_files.items() if d is not None
        }
        try:
            proposal = propose_challenge(client, fixture, ctx.claim, context_files)
        except ChallengeRejectedError as exc:
            self._reject(
                ctx, exc.code, provider=client.transport.provider, model_id=client.model_id[:200]
            )
            return
        except (ModelUnavailableError, ModelBudgetExceededError) as exc:
            self._finish(
                ctx.challenge_id,
                ChallengeStatus.ERROR,
                reason=f"model_{getattr(exc, 'reason', 'unavailable')}"[:64],
                provider=client.transport.provider,
                model_id=client.model_id[:200],
            )
            return

        source = proposal.test_source
        with self._factory.begin() as session:
            put_artifact(
                session,
                ctx.run_id,
                CHALLENGE_TEST_ARTIFACT + ":" + ctx.challenge_id,
                source.encode(),
            )
        try:
            validated = validate_test_source(source)
        except ChallengeRejectedError as exc:
            # Recorded (hashed, stored for review) but never executed.
            self._reject(
                ctx,
                exc.code,
                requirement_id=proposal.requirement_id,
                challenge_type=proposal.challenge_type,
                test_sha256=hashlib.sha256(source.encode()).hexdigest(),
                test_bytes=len(source.encode()),
                provider=client.transport.provider,
                model_id=client.model_id[:200],
            )
            return

        self._event(
            ctx.run_id,
            EventType.CHALLENGE_PROPOSED,
            {
                "challenge_id": ctx.challenge_id,
                "requirement_id": proposal.requirement_id,
                "challenge_type": proposal.challenge_type,
                "test_sha256": validated.sha256,
                "test_bytes": validated.size,
                "test_count": validated.test_count,
                "provider": client.transport.provider,
                "model_id": client.model_id[:200],
            },
        )
        common = {
            "requirement_id": proposal.requirement_id,
            "challenge_type": proposal.challenge_type,
            "test_sha256": validated.sha256,
            "test_bytes": validated.size,
            "test_count": validated.test_count,
            "validated": True,
            "provider": client.transport.provider,
            "model_id": client.model_id[:200],
        }

        baseline = baseline_files(fixture.id)
        if tree_digest(baseline) != fixture.repo_sha:
            self._complete(ctx, CheckOutcome.INCONCLUSIVE, "fixture_digest_mismatch", common)
            return
        tree = verification_tree(baseline, agent_files, fixture.allowed_paths)
        if CHALLENGE_TEST_PATH in tree:
            self._complete(ctx, CheckOutcome.INCONCLUSIVE, "challenge_path_conflict", common)
            return
        tree[CHALLENGE_TEST_PATH] = source.encode()
        try:
            identity = self._runtime.verifier.identity()
            execution = self._runtime.verifier.run_pytest(
                tree, (CHALLENGE_TEST_PATH,), self._runtime.settings.verifier_timeout_seconds
            )
        except VerifierUnavailableError as exc:
            self._complete(ctx, CheckOutcome.INCONCLUSIVE, exc.reason, common)
            return
        with self._factory.begin() as session:
            put_artifact(
                session,
                ctx.run_id,
                CHALLENGE_OUTPUT_ARTIFACT + ":" + ctx.challenge_id,
                execution.excerpt,
            )
        outcome, reason = pytest_outcome(execution)
        self._complete(
            ctx,
            outcome,
            reason,
            common,
            exit_code=execution.exit_code,
            output_sha256=execution.output_sha256,
            output_bytes=execution.output_bytes,
            duration_ms=execution.duration_ms,
            verifier_image_id=identity.image_id,
        )

    def _complete(
        self, ctx: _Context, outcome: CheckOutcome, reason: str, common: dict, **measured
    ) -> None:
        self._event(
            ctx.run_id,
            EventType.CHALLENGE_COMPLETED,
            {
                "challenge_id": ctx.challenge_id,
                "outcome": outcome.value,
                "reason": reason[:200],
                "exit_code": measured.get("exit_code"),
                "output_sha256": measured.get("output_sha256"),
                "output_bytes": measured.get("output_bytes"),
                "duration_ms": measured.get("duration_ms"),
                "image_id": measured.get("verifier_image_id"),
            },
        )
        self._finish(
            ctx.challenge_id,
            ChallengeStatus.COMPLETED,
            outcome=outcome,
            reason=reason[:64],
            **common,
            **measured,
        )
