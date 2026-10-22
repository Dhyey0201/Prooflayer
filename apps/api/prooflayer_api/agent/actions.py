"""Strict schema for the one action a model may propose per step.

Model output is untrusted. It must be a single JSON object matching exactly one
allowlisted action; unknown actions, unknown fields, shell strings and unsafe
paths are rejected before anything reaches a sandbox. There is deliberately no
"run arbitrary command" action: checks are named templates (``AGENT_CHECKS``).
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    TypeAdapter,
    ValidationError,
    field_validator,
)

MAX_WRITE_BYTES = 32_000
MAX_SUMMARY_CHARS = 500
PATH_PATTERN = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_./-]{0,199}$")

# Checks the agent may run on its own workspace. These are observations for the
# agent only; the independent verifier (Commit 09) runs its own pinned suite.
AGENT_CHECKS: dict[str, tuple[str, ...]] = {
    "pytest-smoke": ("tests/test_smoke.py",),
    "pytest-all": ("tests",),
}


def validate_workspace_path(path: str) -> str:
    """Relative POSIX path inside the workspace; no traversal, no absolute paths."""
    if not PATH_PATTERN.fullmatch(path):
        raise ValueError("path must be relative and use only [A-Za-z0-9_./-]")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("path must not contain empty, '.' or '..' segments")
    return path


class _Action(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    # Free-text reasoning is accepted but never stored or executed.
    rationale: str | None = Field(default=None, max_length=300)

    @field_validator("path", check_fields=False)
    @classmethod
    def _safe_path(cls, value: str) -> str:
        return validate_workspace_path(value)


class ListFiles(_Action):
    action: Literal["list_files"]

    @property
    def target(self) -> str:
        return "."


class ReadFile(_Action):
    action: Literal["read_file"]
    path: str

    @property
    def target(self) -> str:
        return self.path


class WriteFile(_Action):
    action: Literal["write_file"]
    path: str
    content: str = Field(max_length=MAX_WRITE_BYTES)

    @field_validator("content")
    @classmethod
    def _bounded_bytes(cls, value: str) -> str:
        if len(value.encode()) > MAX_WRITE_BYTES:
            raise ValueError(f"content exceeds {MAX_WRITE_BYTES} bytes")
        return value

    @property
    def target(self) -> str:
        return self.path


class RunCheck(_Action):
    action: Literal["run_check"]
    check_id: Literal["pytest-smoke", "pytest-all"]

    @property
    def target(self) -> str:
        return self.check_id


class Finish(_Action):
    action: Literal["finish"]
    summary: str = Field(min_length=1, max_length=MAX_SUMMARY_CHARS)
    tests_passed: StrictBool

    @property
    def target(self) -> str:
        return "-"


AgentAction = Annotated[
    ListFiles | ReadFile | WriteFile | RunCheck | Finish, Field(discriminator="action")
]
_ADAPTER: TypeAdapter[AgentAction] = TypeAdapter(AgentAction)
_FENCE = re.compile(r"^```(?:json)?\s*\n(?P<body>.*)\n```$", re.DOTALL)


class InvalidActionError(ValueError):
    """Model output that is not exactly one valid action. ``code`` is safe to log."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def parse_action(text: str) -> AgentAction:
    body = text.strip()
    fenced = _FENCE.match(body)
    if fenced:
        body = fenced.group("body").strip()
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, RecursionError):
        raise InvalidActionError("invalid_json", "response is not a JSON object") from None
    if not isinstance(data, dict):
        raise InvalidActionError("invalid_json", "response must be a single JSON object")
    try:
        return _ADAPTER.validate_python(data)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'action'}: {e['msg']}"
            for e in exc.errors(include_url=False, include_input=False)[:5]
        )
        raise InvalidActionError("schema_violation", errors) from None
