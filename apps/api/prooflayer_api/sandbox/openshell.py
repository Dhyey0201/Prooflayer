"""NVIDIA OpenShell sandbox driver (CLI, OpenShell 0.1.x; developed against v0.1.5 docs).

Every command is an argv list run without a shell; paths are validated by
``agent.actions`` and joined under ``/sandbox/repo``, and file contents travel
on stdin, so neither model output nor fixture content is ever interpreted by a
shell on the host or in the sandbox.

Evidence handling:

* A sandbox counts as enforced only after its log shows ``Landlock ruleset
  built`` with at least one rule applied and no skipped paths. Otherwise it is
  deleted and ``EnforcementUnverifiedError`` is raised: never "secure" by default.
* Filesystem denials are observed from the exec status (Landlock returns
  EACCES; OpenShell does not log per-file denials). Network denials come from
  the sandbox's OCSF log lines (``NET:``/``HTTP:`` ... ``DENIED``).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..agent.actions import AGENT_CHECKS
from .base import (
    Denial,
    EnforcementUnverifiedError,
    ProvisionInfo,
    RuntimeStatus,
    SandboxSpec,
    SandboxUnavailableError,
    ToolOutcome,
    ToolResult,
)
from .policy import REPO_DIR, build_agent_policy, policy_sha256, render_policy
from .workspaces import workspace_listing

MIN_VERSION = (0, 1, 0)  # 0.1.0 removed Dockerfile/directory `--from` sources.
CLI_TIMEOUT_SECONDS = 60.0
CHECK_ENV = ("PYTHONDONTWRITEBYTECODE=1", f"PYTHONPATH={REPO_DIR}")
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_LANDLOCK_BUILT = re.compile(r"Landlock ruleset built \[rules_applied:(\d+) skipped:(\d+)\]")
_OCSF_DENIED = re.compile(
    r"OCSF.*?(?P<cls>NET|HTTP):\S+\s+\[\w+\]\s+DENIED\s+(?P<rest>.*?)\s+"
    r"\[policy:(?P<policy>\S+)\s+engine:(?P<engine>\w+)\]"
)


@dataclass(frozen=True)
class CommandResult:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool = False


class CommandRunner(Protocol):
    def __call__(
        self, argv: Sequence[str], *, input: bytes | None = None, timeout: float
    ) -> CommandResult: ...


def subprocess_runner(
    argv: Sequence[str], *, input: bytes | None = None, timeout: float
) -> CommandResult:
    try:
        # argv list, no shell: arguments are never parsed by a shell.
        completed = subprocess.run(  # noqa: S603
            list(argv), input=input, capture_output=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return CommandResult(returncode=None, stdout=b"", stderr=b"cli_not_found")
    except subprocess.TimeoutExpired as exc:
        return CommandResult(None, exc.stdout or b"", exc.stderr or b"", timed_out=True)
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def parse_version(text: str) -> tuple[int, int, int] | None:
    match = _VERSION.search(text)
    return tuple(int(g) for g in match.groups()) if match else None  # type: ignore[return-value]


def parse_ocsf_denials(log_text: str, *, step_action: str) -> list[tuple[str, Denial]]:
    """(line digest, denial) for each OCSF DENIED network event in ``log_text``."""
    found = []
    for line in log_text.splitlines():
        match = _OCSF_DENIED.search(line)
        if not match:
            continue
        rest = match.group("rest")
        target = rest.split("->", 1)[1].strip() if "->" in rest else rest.split(" ")[-1]
        denial = Denial(
            action=step_action,
            target=target.split("?", 1)[0][:200],
            enforcement_point=match.group("engine"),
            source="ocsf_log",
            enforced=True,
            rule=match.group("policy")[:200],
        )
        found.append((hashlib.sha256(line.encode()).hexdigest(), denial))
    return found


def _is_permission_denied(result: CommandResult) -> bool:
    return result.returncode not in (0, None) and b"Permission denied" in result.stderr


class OpenShellSession:
    def __init__(
        self,
        driver: OpenShellDriver,
        name: str,
        spec: SandboxSpec,
        info: ProvisionInfo,
    ) -> None:
        self._driver = driver
        self._name = name
        self._spec = spec
        self._seen_log_lines: set[str] = set()
        self._last_action = "-"
        self.info = info

    def _exec(
        self,
        argv: Sequence[str],
        *,
        input: bytes | None = None,
        timeout: float = CLI_TIMEOUT_SECONDS,
        env: Sequence[str] = (),
    ) -> CommandResult:
        command = [self._driver.bin, "sandbox", "exec", "-n", self._name, "--no-login-shell"]
        for item in env:
            command += ["--env", item]
        return self._driver.run([*command, "--", *argv], input=input, timeout=timeout)

    def _result(self, action: str, target: str, result: CommandResult) -> ToolResult:
        self._last_action = action
        output = result.stdout + result.stderr
        if result.timed_out:
            return ToolResult.from_output(ToolOutcome.TIMEOUT, None, output, simulated=False)
        if _is_permission_denied(result):
            denial = Denial(action, target, "landlock", "exec_status", enforced=True)
            return ToolResult.from_output(
                ToolOutcome.DENIED, result.returncode, output, simulated=False, denial=denial
            )
        outcome = ToolOutcome.OK if result.returncode == 0 else ToolOutcome.ERROR
        return ToolResult.from_output(outcome, result.returncode, output, simulated=False)

    def list_files(self) -> ToolResult:
        # Names come from the trusted fixture manifest; listing /sandbox/repo would
        # need a directory grant that the policy keeps as narrow as possible.
        self._last_action = "list_files"
        fixture = self._spec.fixture
        listing = workspace_listing(fixture.id, fixture.read_denied_paths)
        return ToolResult.from_output(
            ToolOutcome.OK, 0, ("\n".join(listing) + "\n").encode(), simulated=False
        )

    def read_file(self, path: str) -> ToolResult:
        cap = str(self._spec.max_output_bytes)
        result = self._exec(["head", "-c", cap, "--", f"{REPO_DIR}/{path}"])
        return self._result("read_file", path, result)

    def write_file(self, path: str, content: str) -> ToolResult:
        result = self._exec(["dd", f"of={REPO_DIR}/{path}", "status=none"], input=content.encode())
        return self._result("write_file", path, result)

    def run_check(self, check_id: str, timeout_seconds: float) -> ToolResult:
        targets = [f"{REPO_DIR}/{t}" for t in AGENT_CHECKS[check_id]]
        argv = ["python3", "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets]
        result = self._exec(argv, timeout=timeout_seconds, env=CHECK_ENV)
        return self._result("run_check", check_id, result)

    def drain_denials(self) -> list[Denial]:
        result = self._driver.logs(self._name, since="10m")
        denials = []
        for digest, denial in parse_ocsf_denials(
            result.stdout.decode("utf-8", errors="replace"), step_action=self._last_action
        ):
            if digest not in self._seen_log_lines:
                self._seen_log_lines.add(digest)
                denials.append(denial)
        return denials

    def release(self) -> None:
        self._driver.delete(self._name)


class OpenShellDriver:
    name = "openshell"

    def __init__(
        self,
        *,
        bin: str = "openshell",
        image: str = "prooflayer-workspace:0.1.0",
        cpu: str = "1",
        memory: str = "1Gi",
        runner: CommandRunner = subprocess_runner,
        sleep: Callable[[float], None] = time.sleep,
        enforcement_polls: int = 10,
    ) -> None:
        self.bin = bin
        self._image = image
        self._cpu = cpu
        self._memory = memory
        self.run = runner
        self._sleep = sleep
        self._enforcement_polls = enforcement_polls

    def image_for(self, spec: SandboxSpec) -> str:
        repo, _, tag = self._image.rpartition(":")
        return f"{repo}-{spec.fixture.id.value}:{tag}"

    def probe(self) -> RuntimeStatus:
        version_result = self.run([self.bin, "--version"], timeout=10)
        if version_result.returncode is None and not version_result.timed_out:
            return RuntimeStatus(False, None, "cli_not_found")
        version = parse_version(version_result.stdout.decode(errors="replace"))
        if version_result.returncode != 0 or version is None:
            return RuntimeStatus(False, None, "version_unreadable")
        version_text = ".".join(map(str, version))
        if version < MIN_VERSION:
            return RuntimeStatus(False, version_text, "version_unsupported")
        if self.run([self.bin, "status"], timeout=15).returncode != 0:
            return RuntimeStatus(False, version_text, "gateway_unreachable")
        return RuntimeStatus(True, version_text)

    def logs(self, name: str, *, since: str) -> CommandResult:
        return self.run(
            [self.bin, "logs", name, "--since", since, "--source", "sandbox"],
            timeout=CLI_TIMEOUT_SECONDS,
        )

    def delete(self, name: str) -> None:
        self.run([self.bin, "sandbox", "delete", name], timeout=CLI_TIMEOUT_SECONDS)

    def provision(self, spec: SandboxSpec) -> OpenShellSession:
        status = self.probe()
        if not status.available:
            raise SandboxUnavailableError(status.reason or "unavailable")
        rendered = render_policy(build_agent_policy(spec.fixture))
        name = f"prooflayer-{spec.run_id[:8]}"
        image = self.image_for(spec)
        with tempfile.TemporaryDirectory(prefix="prooflayer-policy-") as tmp:
            policy_file = Path(tmp) / "policy.yaml"
            policy_file.write_text(rendered, encoding="utf-8")
            created = self.run(
                [
                    self.bin,
                    "sandbox",
                    "create",
                    "--name",
                    name,
                    "--from",
                    image,
                    "--policy",
                    str(policy_file),
                    "--cpu",
                    self._cpu,
                    "--memory",
                    self._memory,
                    "--no-auto-providers",
                    "--detach",
                    "--",
                    "sleep",
                    str(spec.timeout_seconds + 60),
                ],
                timeout=CLI_TIMEOUT_SECONDS * 3,
            )
        if created.returncode != 0:
            self.delete(name)
            raise SandboxUnavailableError("sandbox_create_failed")
        try:
            self._confirm_enforcement(name)
        except EnforcementUnverifiedError:
            self.delete(name)
            raise
        info = ProvisionInfo(
            driver="openshell",
            enforced=True,
            policy_sha256=policy_sha256(rendered),
            image=image,
            runtime_version=status.version or "unknown",
        )
        return OpenShellSession(self, name, spec, info)

    def _confirm_enforcement(self, name: str) -> None:
        for _ in range(self._enforcement_polls):
            text = self.logs(name, since="10m").stdout.decode("utf-8", errors="replace")
            if "Skipping inaccessible Landlock path" in text:
                raise EnforcementUnverifiedError("landlock_path_skipped")
            match = _LANDLOCK_BUILT.search(text)
            if match:
                applied, skipped = int(match.group(1)), int(match.group(2))
                if applied > 0 and skipped == 0:
                    return
                raise EnforcementUnverifiedError("landlock_rules_incomplete")
            self._sleep(1.0)
        raise EnforcementUnverifiedError("landlock_not_observed")
