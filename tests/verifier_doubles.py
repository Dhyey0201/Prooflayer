"""Test doubles for the independent verifier.

``ScriptedVerifier`` executes nothing: it returns pytest exit codes chosen by
the test and records the workspace tree it was handed, so tests can assert
what crosses into the verifier. Real execution is covered by
``tests/test_docker_verifier.py`` (opt-in, ``RUN_DOCKER_VERIFIER=1``).
"""

from __future__ import annotations

from collections.abc import Callable

from prooflayer_api.verifier.base import (
    Execution,
    RuntimeIdentity,
    VerifierStatus,
    VerifierUnavailableError,
)

FAKE_IMAGE_ID = "sha256:" + "ab" * 32


class ScriptedVerifier:
    name = "scripted"

    def __init__(
        self,
        exit_code: int | Callable[[dict[str, bytes], tuple[str, ...]], int | None] | None = 0,
        *,
        available: bool = True,
        timed_out: bool = False,
    ) -> None:
        self._exit_code = exit_code
        self._available = available
        self._timed_out = timed_out
        self.calls: list[tuple[dict[str, bytes], tuple[str, ...], float]] = []

    def probe(self) -> VerifierStatus:
        if not self._available:
            return VerifierStatus(False, reason="daemon_unreachable")
        return VerifierStatus(True, FAKE_IMAGE_ID, "test")

    def identity(self) -> RuntimeIdentity:
        if not self._available:
            raise VerifierUnavailableError("daemon_unreachable")
        return RuntimeIdentity(
            "docker", "container", "none", "prooflayer-verifier:0.1.0", FAKE_IMAGE_ID
        )

    def run_pytest(self, files, targets, timeout_seconds) -> Execution:
        self.calls.append((dict(files), tuple(targets), timeout_seconds))
        code = self._exit_code(files, targets) if callable(self._exit_code) else self._exit_code
        if self._timed_out:
            return Execution.from_output(None, b"", 1000, timed_out=True, reason="timeout")
        output = f"scripted verifier exit {code}\n".encode()
        return Execution.from_output(code, output, 12)
