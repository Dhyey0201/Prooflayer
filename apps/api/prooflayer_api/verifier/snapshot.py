"""Workspace snapshots: the trusted baseline, the agent's result and their diff.

The verifier never runs the agent's workspace as-is. It rebuilds the tree from
the pinned fixture baseline and copies in *only* the agent's versions of the
template's ``allowed_paths`` (docs/02 step 5). Tests, helpers and everything
else come from the baseline, so an agent cannot weaken the checks it is graded
by. Changes outside the allowlist are measured separately and fail the
``diff-within-allowlist`` requirement.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
from collections.abc import Mapping
from dataclasses import dataclass

from ..enums import TemplateId
from ..evidence.hashchain import canonical_json, sha256_hex
from ..sandbox.workspaces import workspace_files

MAX_ARCHIVE_BYTES = 8 * 1024 * 1024


def baseline_files(template_id: TemplateId) -> dict[str, bytes]:
    return {path: text.encode() for path, text in workspace_files(template_id).items()}


def tree_digest(files: Mapping[str, bytes | None]) -> str:
    """SHA-256 over sorted ``path -> sha256(content)``; a missing file hashes as null."""
    return sha256_hex(
        canonical_json(
            {
                path: None if data is None else hashlib.sha256(data).hexdigest()
                for path, data in sorted(files.items())
            }
        )
    )


@dataclass(frozen=True)
class WorkspaceDiff:
    changed: tuple[str, ...]
    outside_allowlist: tuple[str, ...]
    # Baseline files the sandbox could not report; the diff is then incomplete.
    unreadable: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.unreadable


def diff_workspace(
    baseline: Mapping[str, bytes],
    observed: Mapping[str, bytes | None],
    allowed_paths: tuple[str, ...],
) -> WorkspaceDiff:
    """Compare what the sandbox holds after the agent ran with the baseline.

    ``observed`` maps each baseline path (and each allowed path) to its bytes,
    or None when the file is absent or could not be read.
    """
    changed, unreadable = [], []
    for path in sorted(set(baseline) | set(observed)):
        before, after = baseline.get(path), observed.get(path)
        if path in baseline and path not in observed:
            unreadable.append(path)
        elif before != after:
            changed.append(path)
    outside = tuple(p for p in changed if p not in allowed_paths)
    return WorkspaceDiff(tuple(changed), outside, tuple(unreadable))


def verification_tree(
    baseline: Mapping[str, bytes],
    agent_files: Mapping[str, bytes | None],
    allowed_paths: tuple[str, ...],
) -> dict[str, bytes]:
    """Baseline plus the agent's allowed files; nothing else crosses over."""
    tree = dict(baseline)
    for path in allowed_paths:
        data = agent_files.get(path)
        if data is None:
            tree.pop(path, None)
        else:
            tree[path] = data
    return tree


def build_archive(files: Mapping[str, bytes]) -> bytes:
    """Deterministic uncompressed tar (fixed order, mtime, owner and modes)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        directories = sorted(
            {"/".join(p.split("/")[:i]) for p in files for i in range(1, p.count("/") + 1)}
        )
        for directory in directories:
            info = tarfile.TarInfo(directory)
            info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, 0
            archive.addfile(info)
        for path in sorted(files):
            info = tarfile.TarInfo(path)
            info.size, info.mode, info.mtime = len(files[path]), 0o644, 0
            archive.addfile(info, io.BytesIO(files[path]))
    data = buffer.getvalue()
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("verification workspace exceeds the archive limit")
    return data
