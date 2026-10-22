"""Run lifecycle: create, read, list and status transitions with evidence events.

Every status change and its event are written in one transaction, so a run's
status is always backed by an event in its hash chain.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ..db.models import Run
from ..enums import Actor, EventType, RunMode, RunStatus, TemplateId
from ..evidence.events import append_event
from ..evidence.hashchain import canonical_json, sha256_hex
from .fixtures import get_fixture
from .state_machine import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    VERDICT_FOR_STATUS,
    check_transition,
)


class RunNotFoundError(Exception):
    pass


class IdempotencyConflictError(Exception):
    """Same Idempotency-Key reused with a different request body."""


class TooManyPendingRunsError(Exception):
    pass


class ConcurrentUpdateError(Exception):
    """Another writer changed the run first (optimistic lock)."""


class LiveModeUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class CreateResult:
    run: Run
    replayed: bool


def _request_digest(template_id: TemplateId, mode: RunMode) -> str:
    return sha256_hex(canonical_json({"template_id": template_id.value, "mode": mode.value}))


def create_run(
    session: Session,
    *,
    template_id: TemplateId,
    mode: RunMode,
    max_pending_runs: int,
    idempotency_key: str | None = None,
    actor: Actor = Actor.API,
    live_available: bool = False,
) -> CreateResult:
    """Create a run in ``queued`` state. Commits on success.

    ``live`` needs a live model and an enforcing sandbox (``live_available``);
    ``replay`` has no runtime yet. Neither is ever silently downgraded.
    """
    if mode is RunMode.REPLAY or (mode is RunMode.LIVE and not live_available):
        raise LiveModeUnavailableError(mode)

    digest = _request_digest(template_id, mode)
    if idempotency_key is not None:
        existing = session.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
        if existing is not None:
            session.rollback()
            if existing.request_sha256 != digest:
                raise IdempotencyConflictError(idempotency_key)
            return CreateResult(existing, replayed=True)

    pending = session.scalar(
        select(func.count()).select_from(Run).where(Run.status.in_(ACTIVE_STATUSES))
    )
    if pending >= max_pending_runs:
        session.rollback()
        raise TooManyPendingRunsError(pending)

    fixture = get_fixture(template_id)
    now = datetime.now(UTC)
    run = Run(
        id=str(uuid.uuid4()),
        task_id=template_id,
        status=RunStatus.CREATED,
        mode=mode,
        policy_version=fixture.policy_version,
        idempotency_key=idempotency_key,
        request_sha256=digest,
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    session.flush()
    append_event(
        session,
        run.id,
        EventType.RUN_CREATED,
        actor,
        {
            "template_id": template_id.value,
            "mode": mode.value,
            "policy_version": fixture.policy_version,
        },
    )
    _apply_transition(session, run, RunStatus.QUEUED, reason="accepted", actor=actor)
    try:
        session.commit()
    except IntegrityError:
        # A concurrent request with the same Idempotency-Key won the race.
        session.rollback()
        if idempotency_key is None:
            raise
        existing = session.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
        if existing is None:
            raise
        if existing.request_sha256 != digest:
            raise IdempotencyConflictError(idempotency_key) from None
        return CreateResult(existing, replayed=True)
    return CreateResult(run, replayed=False)


def get_run(session: Session, run_id: str) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise RunNotFoundError(run_id)
    return run


def list_runs(session: Session, limit: int = 50) -> list[Run]:
    return list(session.scalars(select(Run).order_by(Run.created_at.desc()).limit(limit)))


def _apply_transition(
    session: Session,
    run: Run,
    target: RunStatus,
    *,
    reason: str,
    actor: Actor,
    model_id: str | None = None,
    error_code: str | None = None,
) -> None:
    run_id, current = run.id, RunStatus(run.status)
    check_transition(current, target)
    now = datetime.now(UTC)
    run.status = target
    run.updated_at = now
    if model_id is not None:
        run.model_id = model_id
    if error_code is not None:
        run.error_code = error_code
    if target is RunStatus.RUNNING:
        run.started_at = now
    if target in TERMINAL_STATUSES:
        run.finished_at = now
    run.verdict = VERDICT_FOR_STATUS.get(target)
    try:
        session.flush()
    except StaleDataError as exc:
        raise ConcurrentUpdateError(run_id) from exc
    append_event(
        session,
        run_id,
        EventType.RUN_STATUS_CHANGED,
        actor,
        {"from_status": current.value, "to_status": target.value, "reason": reason},
    )


def transition_run(
    session: Session,
    run_id: str,
    target: RunStatus,
    *,
    reason: str,
    actor: Actor,
    model_id: str | None = None,
    error_code: str | None = None,
) -> Run:
    """Move a run to ``target`` and record the event. Commits on success.

    Raises ``InvalidTransitionError`` for transitions the state machine forbids.
    """
    run = get_run(session, run_id)
    try:
        _apply_transition(
            session,
            run,
            target,
            reason=reason,
            actor=actor,
            model_id=model_id,
            error_code=error_code,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return run


def cancel_run(session: Session, run_id: str, *, actor: Actor = Actor.API) -> Run:
    """Cancel an active run. Idempotent for an already-canceled run."""
    run = get_run(session, run_id)
    if run.status == RunStatus.CANCELED:
        session.rollback()
        return run
    return transition_run(session, run_id, RunStatus.CANCELED, reason="user_requested", actor=actor)


def record_agent_claim(session: Session, run_id: str, *, summary: str, tests_passed: bool) -> Run:
    """Store the agent's untrusted claim with its digest in the hash chain. Commits."""
    run = get_run(session, run_id)
    try:
        run.agent_claim = summary
        run.updated_at = datetime.now(UTC)
        try:
            session.flush()
        except StaleDataError as exc:
            raise ConcurrentUpdateError(run_id) from exc
        append_event(
            session,
            run_id,
            EventType.AGENT_CLAIMED,
            Actor.ORCHESTRATOR,
            {
                "claim_sha256": sha256_hex(summary.encode()),
                "claim_chars": len(summary),
                "tests_passed": tests_passed,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return run


def next_queued_run_id(session: Session) -> str | None:
    run_id = session.scalar(
        select(Run.id).where(Run.status == RunStatus.QUEUED).order_by(Run.created_at).limit(1)
    )
    session.rollback()
    return run_id


def interrupted_run_ids(session: Session) -> list[str]:
    """Runs a previous worker left mid-flight (provisioning/running/verifying)."""
    ids = list(
        session.scalars(
            select(Run.id).where(
                Run.status.in_((RunStatus.PROVISIONING, RunStatus.RUNNING, RunStatus.VERIFYING))
            )
        )
    )
    session.rollback()
    return ids
