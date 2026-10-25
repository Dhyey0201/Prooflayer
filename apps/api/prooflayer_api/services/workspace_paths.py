"""Which workspace paths the orchestrator reads back from the agent sandbox."""

from __future__ import annotations

from ..sandbox.workspaces import workspace_files
from .fixtures import FixtureTemplate


def snapshot_paths(fixture: FixtureTemplate) -> list[str]:
    """Every baseline file plus every allowed path; read-denied paths never."""
    paths = set(workspace_files(fixture.id)) | set(fixture.allowed_paths)
    return sorted(paths - set(fixture.read_denied_paths))
