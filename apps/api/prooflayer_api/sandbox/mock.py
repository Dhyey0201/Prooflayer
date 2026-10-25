"""Deterministic in-memory sandbox for CI and fixture mode without OpenShell.

It models the generated policy (read-denied paths unreadable, only
``allowed_paths`` writable) so the agent loop behaves the same, but it
enforces nothing: every provision reports ``enforced=False``, every denial
``enforced=False, source="mock_policy"``, and checks are *simulated*, not run.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..agent.actions import AGENT_CHECKS
from .base import (
    Denial,
    ProvisionInfo,
    RuntimeStatus,
    SandboxSpec,
    ToolOutcome,
    ToolResult,
)
from .policy import build_agent_policy, policy_sha256, render_policy
from .workspaces import workspace_files, workspace_listing

MOCK_VERSION = "mock-0.1.0"


class MockSandboxSession:
    def __init__(self, spec: SandboxSpec) -> None:
        fixture = spec.fixture
        self._fixture = fixture
        self._files = workspace_files(fixture.id)
        self._max_output = spec.max_output_bytes
        self.released = False
        self.info = ProvisionInfo(
            driver="mock",
            enforced=False,
            policy_sha256=policy_sha256(render_policy(build_agent_policy(fixture))),
            image="in-memory",
            runtime_version=MOCK_VERSION,
        )

    def _denied(self, action: str, path: str, rule: str) -> ToolResult:
        message = f"{path}: Permission denied (mock policy; not enforced by a runtime)\n"
        return ToolResult.from_output(
            ToolOutcome.DENIED,
            1,
            message.encode(),
            simulated=True,
            denial=Denial(action, path, "mock", "mock_policy", enforced=False, rule=rule),
        )

    def list_files(self) -> ToolResult:
        listing = workspace_listing(self._fixture.id, self._fixture.read_denied_paths)
        return ToolResult.from_output(
            ToolOutcome.OK, 0, ("\n".join(listing) + "\n").encode(), simulated=True
        )

    def read_file(self, path: str) -> ToolResult:
        if path in self._fixture.read_denied_paths:
            return self._denied("read_file", path, "read_denied_paths")
        if path not in self._files:
            return ToolResult.from_output(
                ToolOutcome.ERROR, 1, f"{path}: No such file\n".encode(), simulated=True
            )
        data = self._files[path].encode()
        return ToolResult.from_output(
            ToolOutcome.OK,
            0,
            data[: self._max_output],
            simulated=True,
            truncated=len(data) > self._max_output,
        )

    def write_file(self, path: str, content: str) -> ToolResult:
        if path not in self._fixture.allowed_paths:
            return self._denied("write_file", path, "allowed_paths")
        self._files[path] = content
        return ToolResult.from_output(ToolOutcome.OK, 0, b"", simulated=True)

    def run_check(self, check_id: str, timeout_seconds: float) -> ToolResult:
        if check_id not in AGENT_CHECKS:
            return ToolResult.from_output(ToolOutcome.ERROR, 2, b"unknown check\n", simulated=True)
        # Nothing executes here; say so instead of inventing a pass.
        message = f"SIMULATED: {check_id} was not executed (mock sandbox, no test runtime).\n"
        return ToolResult.from_output(ToolOutcome.OK, None, message.encode(), simulated=True)

    def drain_denials(self) -> list[Denial]:
        return []

    def snapshot(self, paths: Sequence[str]) -> dict[str, bytes | None]:
        return {p: self._files[p].encode() if p in self._files else None for p in paths}

    def file_content(self, path: str) -> str | None:
        """Test helper: the workspace state after the agent ran."""
        return self._files.get(path)

    def release(self) -> None:
        self.released = True


class MockSandboxDriver:
    name = "mock"

    def __init__(self) -> None:
        self.sessions: list[MockSandboxSession] = []

    def probe(self) -> RuntimeStatus:
        return RuntimeStatus(available=True, version=MOCK_VERSION)

    def provision(self, spec: SandboxSpec) -> MockSandboxSession:
        session = MockSandboxSession(spec)
        self.sessions.append(session)
        return session
