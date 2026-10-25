"""Typed boundary between ProofLayer and an independent verification runtime.

A verifier driver executes one pinned pytest invocation against a workspace
tree in a fresh, isolated environment and reports measurements only: exit
code, output size and SHA-256, duration and the runtime identity. It is never
given the agent's sandbox, its credentials or its tools.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

# Output kept from one verifier execution (hashed in full, stored up to this cap).
MAX_VERIFIER_OUTPUT = 64_000


@dataclass(frozen=True)
class VerifierStatus:
    available: bool
    # Runtime identity recorded with every check, e.g. the image ID.
    image_id: str | None = None
    version: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Execution:
    """One pinned command run by the verifier. ``exit_code`` None = no result."""

    exit_code: int | None
    output_sha256: str
    output_bytes: int
    # First MAX_VERIFIER_OUTPUT bytes, kept as a content-addressed artifact.
    excerpt: bytes
    duration_ms: int
    timed_out: bool = False
    # Short machine-readable reason when no exit code was obtained.
    reason: str | None = None

    @classmethod
    def from_output(
        cls,
        exit_code: int | None,
        output: bytes,
        duration_ms: int,
        *,
        timed_out: bool = False,
        reason: str | None = None,
    ) -> Execution:
        return cls(
            exit_code=exit_code,
            output_sha256=hashlib.sha256(output).hexdigest(),
            output_bytes=len(output),
            excerpt=output[:MAX_VERIFIER_OUTPUT],
            duration_ms=duration_ms,
            timed_out=timed_out,
            reason=reason,
        )


@dataclass(frozen=True)
class RuntimeIdentity:
    driver: str
    # "container": separate container with no network; never the agent sandbox.
    isolation: str
    network: str
    image: str
    image_id: str


class VerifierUnavailableError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class VerifierDriver(Protocol):
    name: str

    def probe(self) -> VerifierStatus: ...

    def identity(self) -> RuntimeIdentity:
        """Identity of the runtime; raises ``VerifierUnavailableError``."""
        ...

    def run_pytest(
        self, files: dict[str, bytes], targets: tuple[str, ...], timeout_seconds: float
    ) -> Execution: ...


class UnavailableVerifier:
    """Configured when no verifier runtime is allowed (``VERIFIER_DRIVER=disabled``)."""

    name = "disabled"

    def probe(self) -> VerifierStatus:
        return VerifierStatus(False, reason="verifier_disabled")

    def identity(self) -> RuntimeIdentity:
        raise VerifierUnavailableError("verifier_disabled")

    def run_pytest(
        self, files: dict[str, bytes], targets: tuple[str, ...], timeout_seconds: float
    ) -> Execution:
        raise VerifierUnavailableError("verifier_disabled")
