"""Content-addressed evidence blobs stored in the ``artifacts`` table.

Blobs are small (verifier output excerpts, the agent's allowed files, generated
challenge tests) and never contain secrets: the verifier and the challenge
proposer never see read-denied files. Reads re-hash the content, so a modified
blob is detected rather than trusted.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Artifact

MAX_ARTIFACT_BYTES = 256_000


class ArtifactIntegrityError(Exception):
    pass


def put_artifact(session: Session, run_id: str, kind: str, data: bytes) -> Artifact:
    """Store ``data`` for ``run_id`` in the caller's transaction (deduplicated by hash)."""
    if len(data) > MAX_ARTIFACT_BYTES:
        raise ValueError(f"artifact exceeds {MAX_ARTIFACT_BYTES} bytes")
    digest = hashlib.sha256(data).hexdigest()
    existing = session.scalar(
        select(Artifact).where(
            Artifact.run_id == run_id, Artifact.type == kind, Artifact.content_sha256 == digest
        )
    )
    if existing is not None:
        return existing
    artifact = Artifact(
        id=str(uuid.uuid4()),
        run_id=run_id,
        type=kind,
        content_sha256=digest,
        location="db",
        size_bytes=len(data),
        content=data,
    )
    session.add(artifact)
    session.flush()
    return artifact


def latest_artifact(session: Session, run_id: str, kind: str) -> Artifact | None:
    return session.scalar(
        select(Artifact)
        .where(Artifact.run_id == run_id, Artifact.type == kind)
        .order_by(Artifact.created_at.desc())
        .limit(1)
    )


def read_artifact(artifact: Artifact) -> bytes:
    data = artifact.content or b""
    if hashlib.sha256(data).hexdigest() != artifact.content_sha256:
        raise ArtifactIntegrityError(artifact.id)
    return data


def list_artifacts(session: Session, run_id: str) -> list[Artifact]:
    return list(
        session.scalars(
            select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at)
        )
    )
