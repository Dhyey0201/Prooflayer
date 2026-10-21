"""Trusted fixture workspaces (``fixture_workspaces/<template_id>/``).

Read-denied paths (``.env.production``) are not committed. In the OpenShell
image they are symlinks into ``/sandbox/secrets``, which no policy grants, so
Landlock denies the open; the mock driver models the same rule in memory.
"""

from __future__ import annotations

from pathlib import Path

from ..enums import TemplateId
from .base import SandboxUnavailableError

WORKSPACE_ROOT = Path(__file__).resolve().parents[1] / "fixture_workspaces"


def workspace_dir(template_id: TemplateId) -> Path:
    path = WORKSPACE_ROOT / template_id.value
    if not path.is_dir():
        raise SandboxUnavailableError("fixture_workspace_missing")
    return path


def workspace_files(template_id: TemplateId) -> dict[str, str]:
    """Committed files of a workspace, keyed by POSIX path relative to its root."""
    root = workspace_dir(template_id)
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def workspace_listing(template_id: TemplateId, read_denied_paths: tuple[str, ...]) -> list[str]:
    """File names the agent sees. Denied paths are listed (they exist) but unreadable."""
    return sorted({*workspace_files(template_id), *read_denied_paths})
