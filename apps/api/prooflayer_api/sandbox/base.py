"""Typed boundary between the orchestrator and an agent sandbox runtime.

A driver provisions one isolated workspace per run and executes only the
allowlisted agent actions in it. Results carry measurements (exit code, byte
count, SHA-256) plus a bounded observation for the agent; the orchestrator
persists the measurements, never the output itself.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ..services.fixtures import FixtureTemplate

# Bytes of tool output shown back to the agent per step (never persisted).
OBSERVATION_LIMIT = 8_000


class ToolOutcome(StrEnum):
    OK = "ok"
    # Stopped at the enforcement point. An attempt, never a disclosure.
    DENIED = "denied"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class Denial:
    action: str
    target: str
    # Where the decision was made: "landlock", "opa", "l7", "ssrf" or "mock".
    enforcement_point: str
    # What observed it: "exec_status", "ocsf_log" or "mock_policy".
    source: str
    # True only when a real runtime enforced it; the mock always reports False.
    enforced: bool
    rule: str = "-"


@dataclass(frozen=True)
class ToolResult:
    outcome: ToolOutcome
    exit_code: int | None
    observation: str
    output_bytes: int
    output_sha256: str
    truncated: bool
    # True when nothing was executed (mock driver); the agent is told so.
    simulated: bool
    denial: Denial | None = None

    @classmethod
    def from_output(
        cls,
        outcome: ToolOutcome,
        exit_code: int | None,
        output: bytes,
        *,
        simulated: bool,
        truncated: bool = False,
        denial: Denial | None = None,
    ) -> ToolResult:
        return cls(
            outcome=outcome,
            exit_code=exit_code,
            observation=output[:OBSERVATION_LIMIT].decode("utf-8", errors="replace"),
            output_bytes=len(output),
            output_sha256=hashlib.sha256(output).hexdigest(),
            truncated=truncated or len(output) > OBSERVATION_LIMIT,
            simulated=simulated,
            denial=denial,
        )


@dataclass(frozen=True)
class SandboxSpec:
    run_id: str
    fixture: FixtureTemplate
    timeout_seconds: int
    max_output_bytes: int


@dataclass(frozen=True)
class RuntimeStatus:
    available: bool
    version: str | None
    # Short machine-readable reason when unavailable, e.g. "cli_not_found".
    reason: str | None = None


@dataclass(frozen=True)
class ProvisionInfo:
    driver: str
    # True only when the runtime confirmed its policy is active for this sandbox.
    enforced: bool
    policy_sha256: str
    image: str
    runtime_version: str


class SandboxUnavailableError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class EnforcementUnverifiedError(Exception):
    """The sandbox started but its policy could not be confirmed active."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SandboxSession(Protocol):
    info: ProvisionInfo

    def list_files(self) -> ToolResult: ...

    def read_file(self, path: str) -> ToolResult: ...

    def write_file(self, path: str, content: str) -> ToolResult: ...

    def run_check(self, check_id: str, timeout_seconds: float) -> ToolResult: ...

    def drain_denials(self) -> list[Denial]:
        """Denials observed out of band (e.g. network) since the last call."""
        ...

    def snapshot(self, paths: Sequence[str]) -> dict[str, bytes | None]:
        """Current bytes of each path after the agent ran (None = absent).

        A path that could not be read reliably is left out, so the verifier
        reports the workspace diff as incomplete instead of guessing.
        """
        ...

    def release(self) -> None: ...


class SandboxDriver(Protocol):
    name: str

    def probe(self) -> RuntimeStatus: ...

    def provision(self, spec: SandboxSpec) -> SandboxSession: ...
