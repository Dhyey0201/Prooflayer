"""SQLAlchemy models for the data model in docs/02_ARCHITECTURE_SECURITY.md.

Behaviour lives in ``prooflayer_api.services`` and ``prooflayer_api.evidence``.
Schema changes go through Alembic migrations in ``apps/api/migrations``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..enums import ChallengeStatus, CheckOutcome, RunMode, RunStatus, TemplateId, Verdict

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _enum(enum_cls: type, name: str) -> Enum:
    # Store enum *values* (the contract strings) as non-native VARCHAR with a CHECK.
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda e: [m.value for m in e],
        length=32,
    )


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[TemplateId] = mapped_column(_enum(TemplateId, "template_id"), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    repo_sha: Mapped[str] = mapped_column(String(64))
    allowed_paths_json: Mapped[list] = mapped_column(JSON)
    required_checks_json: Mapped[list] = mapped_column(JSON)
    policy_version: Mapped[str] = mapped_column(String(32))


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[TemplateId] = mapped_column(
        _enum(TemplateId, "run_template_id"), ForeignKey("task_templates.id"), index=True
    )
    status: Mapped[RunStatus] = mapped_column(_enum(RunStatus, "run_status"), index=True)
    mode: Mapped[RunMode] = mapped_column(_enum(RunMode, "run_mode"))
    verdict: Mapped[Verdict | None] = mapped_column(_enum(Verdict, "run_verdict"), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Untrusted agent text; stored as evidence input, never as a verdict.
    agent_claim: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    worktree_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Optimistic lock: every UPDATE checks and bumps this (StaleDataError on a race).
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    # Optional client Idempotency-Key for POST /runs, with a digest of the request body.
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    request_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_events_run_id_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    type: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(64))
    # Allowlisted, redacted fields only.
    payload_json: Mapped[dict] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), index=True)
    type: Mapped[str] = mapped_column(String(64))
    content_sha256: Mapped[str] = mapped_column(String(64))
    location: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # Small evidence blobs (verifier output, agent workspace, challenge test)
    # stored inline, content-addressed by ``content_sha256``; location is "db".
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), index=True)
    requirement_id: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[CheckOutcome] = mapped_column(_enum(CheckOutcome, "check_outcome"))
    evidence_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    command_template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    measurements_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), unique=True)
    schema_version: Mapped[str] = mapped_column(String(16))
    verdict: Mapped[Verdict] = mapped_column(_enum(Verdict, "certificate_verdict"))
    json_sha256: Mapped[str] = mapped_column(String(64))
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # The exact certificate served by the API; ``json_sha256`` is its canonical digest.
    body_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Challenge(Base):
    """A model-proposed test, validated and run by the verifier after certification."""

    __tablename__ = "challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), index=True)
    status: Mapped[ChallengeStatus] = mapped_column(
        _enum(ChallengeStatus, "challenge_status"), index=True
    )
    requirement_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    challenge_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Untrusted model-written test source, stored as an artifact (sha256 here).
    test_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    test_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outcome: Mapped[CheckOutcome | None] = mapped_column(
        _enum(CheckOutcome, "challenge_outcome"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verifier_image_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, server_default="1")

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
