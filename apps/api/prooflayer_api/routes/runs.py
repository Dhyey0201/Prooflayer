"""Template, run and event routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db.deps import get_session
from ..db.models import Certificate, Check
from ..enums import ErrorCode, RunMode
from ..errors import ApiError
from ..evidence.events import event_to_wire, list_events
from ..schemas import ChallengeOut, CheckOut, EventOut, RunCreate, RunOut, TemplateOut
from ..services import challenges as challenge_service
from ..services import runs as run_service
from ..services.fixtures import FIXTURES, get_fixture
from ..services.runtime import live_runtime_available
from ..services.state_machine import InvalidTransitionError
from .system import SandboxStatusDep

router = APIRouter(tags=["runs"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9_-]{8,128}$"


def _run_or_404(session: Session, run_id: uuid.UUID):
    try:
        return run_service.get_run(session, str(run_id))
    except run_service.RunNotFoundError:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Run not found") from None


@router.get("/templates", response_model=list[TemplateOut], operation_id="listTemplates")
def list_templates() -> list[TemplateOut]:
    return [TemplateOut.from_fixture(fixture) for fixture in FIXTURES.values()]


@router.get("/runs", response_model=list[RunOut], operation_id="listRuns")
def list_runs(session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 50) -> list[RunOut]:
    return [RunOut.from_model(run) for run in run_service.list_runs(session, limit)]


@router.post(
    "/runs",
    response_model=RunOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="createRun",
)
def create_run(
    body: RunCreate,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    sandbox: SandboxStatusDep,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_KEY_PATTERN)
    ] = None,
) -> RunOut:
    try:
        result = run_service.create_run(
            session,
            template_id=body.template_id,
            mode=body.mode,
            max_pending_runs=settings.max_pending_runs,
            idempotency_key=idempotency_key,
            live_available=body.mode is RunMode.LIVE and live_runtime_available(settings, sandbox),
        )
    except run_service.LiveModeUnavailableError:
        raise ApiError(
            422,
            ErrorCode.VALIDATION_ERROR,
            f"Mode '{body.mode}' is not available: live runs need a live model and an "
            "enforcing OpenShell sandbox",
        ) from None
    except run_service.IdempotencyConflictError:
        raise ApiError(
            409, ErrorCode.CONFLICT, "Idempotency-Key was already used with a different request"
        ) from None
    except run_service.TooManyPendingRunsError:
        raise ApiError(429, ErrorCode.RATE_LIMITED, "Too many pending runs; retry later") from None
    if result.replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return RunOut.from_model(result.run)


@router.get("/runs/{run_id}", response_model=RunOut, operation_id="getRun")
def get_run(run_id: uuid.UUID, session: SessionDep) -> RunOut:
    return RunOut.from_model(_run_or_404(session, run_id))


@router.get("/runs/{run_id}/events", response_model=list[EventOut], operation_id="getRunEvents")
def get_run_events(
    run_id: uuid.UUID,
    session: SessionDep,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> list[EventOut]:
    run = _run_or_404(session, run_id)
    return [EventOut(**event_to_wire(e)) for e in list_events(session, run.id, after_seq, limit)]


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RunOut,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="cancelRun",
)
def cancel_run(run_id: uuid.UUID, session: SessionDep) -> RunOut:
    _run_or_404(session, run_id)
    try:
        run = run_service.cancel_run(session, str(run_id))
    except InvalidTransitionError as exc:
        raise ApiError(409, ErrorCode.CONFLICT, f"Run is already {exc.current}") from None
    except run_service.ConcurrentUpdateError:
        raise ApiError(409, ErrorCode.CONFLICT, "Run changed concurrently; retry") from None
    return RunOut.from_model(run)


@router.get("/runs/{run_id}/checks", response_model=list[CheckOut], operation_id="listChecks")
def list_checks(run_id: uuid.UUID, session: SessionDep) -> list[CheckOut]:
    run = _run_or_404(session, run_id)
    order = {r: i for i, r in enumerate(get_fixture(run.task_id).required_checks)}
    checks = session.scalars(select(Check).where(Check.run_id == run.id))
    return [
        CheckOut.from_model(c)
        for c in sorted(checks, key=lambda c: order.get(c.requirement_id, len(order)))
    ]


@router.get("/runs/{run_id}/certificate", operation_id="getCertificate")
def get_certificate(run_id: uuid.UUID, session: SessionDep) -> JSONResponse:
    run = _run_or_404(session, run_id)
    certificate = session.scalar(select(Certificate).where(Certificate.run_id == run.id))
    if certificate is None or certificate.body_json is None:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Certificate not ready")
    return JSONResponse(
        certificate.body_json, headers={"X-Certificate-SHA256": certificate.json_sha256}
    )


@router.post(
    "/runs/{run_id}/challenge",
    response_model=ChallengeOut,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startChallenge",
)
def start_challenge(run_id: uuid.UUID, session: SessionDep, settings: SettingsDep) -> ChallengeOut:
    _run_or_404(session, run_id)
    try:
        challenge = challenge_service.request_challenge(
            session, str(run_id), max_per_run=settings.max_challenges_per_run
        )
    except challenge_service.ChallengeNotAllowedError as exc:
        raise ApiError(409, ErrorCode.CONFLICT, f"Cannot challenge yet: {exc.reason}") from None
    except challenge_service.ChallengeLimitError:
        raise ApiError(
            429, ErrorCode.RATE_LIMITED, "Challenge limit reached for this run"
        ) from None
    return ChallengeOut.from_model(challenge, None)


@router.get(
    "/runs/{run_id}/challenges", response_model=list[ChallengeOut], operation_id="listChallenges"
)
def list_challenges(run_id: uuid.UUID, session: SessionDep) -> list[ChallengeOut]:
    run = _run_or_404(session, run_id)
    return [
        ChallengeOut.from_model(c, challenge_service.challenge_test_source(session, c))
        for c in challenge_service.list_challenges(session, run.id)
    ]
