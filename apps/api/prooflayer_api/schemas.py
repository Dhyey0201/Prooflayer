"""Wire models for run, event and template endpoints (contracts/openapi.yaml)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from .db.models import Run
from .enums import RunMode, RunStatus, TemplateId, Verdict
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
