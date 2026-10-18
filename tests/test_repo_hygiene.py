"""Secrets must stay out of git; only the example env file is tracked."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")

needs_git = pytest.mark.skipif(
    GIT is None or not (ROOT / ".git").exists(), reason="requires a git checkout"
)

# Real-looking key shapes. Placeholders in .env.example must not match these.
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{32,}"),
    re.compile(r"tvly-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [GIT, *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


@needs_git
@pytest.mark.parametrize(
    "path",
    [".env", ".env.local", ".env.production", "apps/api/.env", "data/prooflayer.db", ".venv/x"],
)
def test_sensitive_paths_are_ignored(path: str) -> None:
    assert _git("check-ignore", "-q", path).returncode == 0, path


@needs_git
def test_env_example_is_not_ignored() -> None:
    assert _git("check-ignore", "-q", ".env.example").returncode == 1


@needs_git
def test_no_env_files_tracked() -> None:
    tracked = _git("ls-files").stdout.splitlines()
    env_files = [p for p in tracked if Path(p).name.startswith(".env")]
    assert set(env_files) <= {".env.example"}


def test_env_example_has_no_real_values() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^NEBIUS_API_KEY=\s*$", example, re.MULTILINE)
    assert re.search(r"^PROOFLAYER_MOCK_MODE=true\s*$", example, re.MULTILINE)


@needs_git
def test_tracked_files_contain_no_secret_shapes() -> None:
    hits = []
    for rel in _git("ls-files").stdout.splitlines():
        path = ROOT / rel
        if not path.is_file() or path.suffix in {".png", ".jpg", ".ico", ".docx"}:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        hits += [f"{rel}: {p.pattern}" for p in SECRET_PATTERNS if p.search(content)]
    assert hits == []


def test_license_is_mit() -> None:
    assert "MIT License" in (ROOT / "LICENSE").read_text(encoding="utf-8")
