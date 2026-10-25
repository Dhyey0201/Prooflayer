"""Wire models for run, event and template endpoints (contracts/openapi.yaml)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from .db.models import Challenge, Check, Run
from .enums import ChallengeStatus, CheckOutcome, RunMode, RunStatus, TemplateId, Verdict
from .evidence.hashchain import format_timestamp
from .services.fixtures import FixtureTemplate


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: TemplateId
    mode: RunMode = RunMode.FIXTURE


class RunOut(BaseModel):
    id: str
    template_id: TemplateId
    status: RunStatus
    mode: RunMode
    created_at: datetime
    updated_at: datetime
    # Untrusted agent text, shown as a claim; never evidence of success.
    agent_claim: str | None
    verdict: Verdict | None

    @field_serializer("created_at", "updated_at")
    def _utc(self, value: datetime) -> str:
        return format_timestamp(value)

    @classmethod
    def from_model(cls, run: Run) -> RunOut:
        return cls(
            id=run.id,
            template_id=run.task_id,
            status=run.status,
            mode=run.mode,
            created_at=run.created_at,
            updated_at=run.updated_at,
            agent_claim=run.agent_claim,
            verdict=run.verdict,
        )


class EventOut(BaseModel):
    run_id: str
    seq: int
    timestamp: str
    event_type: str
    actor: str
    safe_payload: dict[str, Any]
    previous_hash: str
    event_hash: str


class TemplateOut(BaseModel):
    id: TemplateId
    title: str
    description: str
    allowed_paths: list[str]
    read_denied_paths: list[str]
    required_checks: list[str]
    policy_version: str
    repo_sha: str
    # Benchmark ground truth for this fixture; NOT the outcome of any run.
    expected_verdict: Verdict

    @classmethod
    def from_fixture(cls, fixture: FixtureTemplate) -> TemplateOut:
        return cls(
            id=fixture.id,
            title=fixture.title,
            description=fixture.description,
            allowed_paths=list(fixture.allowed_paths),
            read_denied_paths=list(fixture.read_denied_paths),
            required_checks=list(fixture.required_checks),
            policy_version=fixture.policy_version,
            repo_sha=fixture.repo_sha,
            expected_verdict=fixture.expected_verdict,
        )


class CheckOut(BaseModel):
    """One independent check result; measured by the verifier, never by the agent."""

    requirement_id: str
    kind: str
    outcome: CheckOutcome
    reason: str | None
    command_template_id: str | None
    exit_code: int | None
    output_sha256: str | None
    duration_ms: int | None
    evidence_ref: str | None
    measurements: dict[str, Any]

    @classmethod
    def from_model(cls, check: Check) -> CheckOut:
        return cls(
            requirement_id=check.requirement_id,
            kind=check.kind,
            outcome=check.outcome,
            reason=check.reason,
            command_template_id=check.command_template_id,
            exit_code=check.exit_code,
            output_sha256=check.output_sha256,
            duration_ms=check.duration_ms,
            evidence_ref=check.evidence_ref,
            measurements=check.measurements_json or {},
        )


class ChallengeOut(BaseModel):
    id: str
    run_id: str
    status: ChallengeStatus
    requirement_id: str | None
    challenge_type: str | None
    # False: rejected by static validation and never executed.
    validated: bool | None
    # Set only once the verifier ran the test; never derived from the model.
    outcome: CheckOutcome | None
    reason: str | None
    test_sha256: str | None
    test_bytes: int | None
    test_count: int | None
    # Untrusted model-written source, shown for review only.
    test_source: str | None
    exit_code: int | None
    output_sha256: str | None
    output_bytes: int | None
    duration_ms: int | None
    provider: str | None
    model_id: str | None
    verifier_image_id: str | None
    created_at: datetime
    finished_at: datetime | None

    @field_serializer("created_at", "finished_at")
    def _utc(self, value: datetime | None) -> str | None:
        return None if value is None else format_timestamp(value)

    @classmethod
    def from_model(cls, challenge: Challenge, test_source: str | None) -> ChallengeOut:
        return cls(
            id=challenge.id,
            run_id=challenge.run_id,
            status=challenge.status,
            requirement_id=challenge.requirement_id,
            challenge_type=challenge.challenge_type,
            validated=challenge.validated,
            outcome=challenge.outcome,
            reason=challenge.reason,
            test_sha256=challenge.test_sha256,
            test_bytes=challenge.test_bytes,
            test_count=challenge.test_count,
            test_source=test_source,
            exit_code=challenge.exit_code,
            output_sha256=challenge.output_sha256,
            output_bytes=challenge.output_bytes,
            duration_ms=challenge.duration_ms,
            provider=challenge.provider,
            model_id=challenge.model_id,
            verifier_image_id=challenge.verifier_image_id,
            created_at=challenge.created_at,
            finished_at=challenge.finished_at,
        )
