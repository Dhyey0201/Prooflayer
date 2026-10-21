"""OpenShellDriver against a fake CLI runner.

The fake replays output formats from the OpenShell v0.1.5 documentation
(``docs/observability/logging.mdx``). It proves the driver's command
construction and evidence parsing, NOT that OpenShell enforces anything; the
real check is ``test_live_integration.py`` (opt-in).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from prooflayer_api.enums import TemplateId
from prooflayer_api.sandbox.base import (
    EnforcementUnverifiedError,
    SandboxSpec,
    SandboxUnavailableError,
    ToolOutcome,
)
from prooflayer_api.sandbox.openshell import (
    CommandResult,
    OpenShellDriver,
    parse_ocsf_denials,
    parse_version,
)
from prooflayer_api.sandbox.policy import build_agent_policy, render_policy
from prooflayer_api.services.fixtures import get_fixture

LANDLOCK_OK = (
    "OCSF CONFIG:ENABLED [INFO] Landlock filesystem sandbox available [abi:v3 compat:HardRequirement ro:7 rw:3]\n"  # noqa: E501
    "OCSF CONFIG:ENABLED [INFO] Landlock ruleset built [rules_applied:10 skipped:0]\n"
)
NET_DENY = (
    "[1775014132.690] [sandbox] [OCSF ] [ocsf] NET:OPEN [MED] DENIED /usr/bin/curl(64) -> "
    "httpbin.org:443 [policy:- engine:opa] [reason:no matching policy]"
)
HTTP_DENY = (
    "2026-04-01T04:04:32.690Z OCSF HTTP:POST [MED] DENIED POST "
    "https://api.github.com/user/repos?token=x [policy:github_api engine:l7]"
)


class FakeCli:
    def __init__(self, handler: Callable[[list[str], bytes | None], CommandResult]) -> None:
        self.handler = handler
        self.calls: list[tuple[list[str], bytes | None, float]] = []
        self.policy_seen: str | None = None

    def __call__(self, argv: Sequence[str], *, input: bytes | None = None, timeout: float):
        argv = list(argv)
        self.calls.append((argv, input, timeout))
        if argv[1:3] == ["sandbox", "create"]:
            # The policy file must exist while `create` runs.
            self.policy_seen = Path(argv[argv.index("--policy") + 1]).read_text()
        return self.handler(argv, input)

    def commands(self) -> list[list[str]]:
        return [c[0] for c in self.calls]


def ok(stdout: str = "", stderr: str = "") -> CommandResult:
    return CommandResult(0, stdout.encode(), stderr.encode())


def healthy(logs: str = LANDLOCK_OK, exec_result: Callable | None = None):
    def handler(argv: list[str], input: bytes | None) -> CommandResult:
        if argv[1] == "--version":
            return ok("openshell 0.1.5\n")
        if argv[1] == "logs":
            return ok(logs)
        if argv[1:3] == ["sandbox", "exec"] and exec_result is not None:
            return exec_result(argv, input)
        return ok()

    return handler


def spec(template: TemplateId = TemplateId.DENIED_SECRET_READ) -> SandboxSpec:
    return SandboxSpec("0123456789abcdef", get_fixture(template), 120, 1000)


def driver(cli: FakeCli, **kwargs) -> OpenShellDriver:
    return OpenShellDriver(runner=cli, sleep=lambda _s: None, enforcement_polls=3, **kwargs)


# --- probe ------------------------------------------------------------------


def test_parse_version() -> None:
    assert parse_version("openshell 0.1.5") == (0, 1, 5)
    assert parse_version("garbage") is None


@pytest.mark.parametrize(
    ("handler", "reason"),
    [
        (lambda a, i: CommandResult(None, b"", b"cli_not_found"), "cli_not_found"),
        (lambda a, i: ok("no version here"), "version_unreadable"),
        (lambda a, i: ok("openshell 0.0.116"), "version_unsupported"),
        (
            lambda a, i: (
                ok("openshell 0.1.5") if a[1] == "--version" else CommandResult(1, b"", b"")
            ),
            "gateway_unreachable",
        ),
    ],
)
def test_probe_reports_unavailable_with_reason(handler, reason: str) -> None:
    status = driver(FakeCli(handler)).probe()
    assert status.available is False
    assert status.reason == reason


def test_probe_available() -> None:
    cli = FakeCli(healthy())
    status = driver(cli).probe()
    assert (status.available, status.version) == (True, "0.1.5")
    assert cli.commands() == [["openshell", "--version"], ["openshell", "status"]]


# --- provisioning -----------------------------------------------------------


def test_provision_creates_policy_bound_sandbox_and_confirms_landlock() -> None:
    cli = FakeCli(healthy())
    session = driver(cli, image="prooflayer-workspace:0.1.0", cpu="1", memory="1Gi").provision(
        spec()
    )

    create = next(c for c in cli.commands() if c[1:3] == ["sandbox", "create"])
    assert create[create.index("--name") + 1] == "prooflayer-01234567"
    assert create[create.index("--from") + 1] == "prooflayer-workspace-denied-secret-read:0.1.0"
    assert "--no-auto-providers" in create
    assert "--detach" in create
    assert create[create.index("--cpu") + 1] == "1"
    assert create[create.index("--memory") + 1] == "1Gi"
    assert create[-3:] == ["--", "sleep", "180"]
    assert cli.policy_seen == render_policy(build_agent_policy(get_fixture(spec().fixture.id)))
    # The temporary policy file is removed after creation.
    assert not Path(create[create.index("--policy") + 1]).exists()

    assert session.info.enforced is True
    assert session.info.driver == "openshell"
    assert session.info.runtime_version == "0.1.5"


@pytest.mark.parametrize(
    ("logs", "reason"),
    [
        ("", "landlock_not_observed"),
        (
            "OCSF CONFIG:ENABLED [INFO] Landlock ruleset built [rules_applied:9 skipped:1]",
            "landlock_rules_incomplete",
        ),
        (
            "OCSF CONFIG:ENABLED [INFO] Landlock ruleset built [rules_applied:0 skipped:0]",
            "landlock_rules_incomplete",
        ),
        (
            "OCSF CONFIG:OTHER [MED] Skipping inaccessible Landlock path (best-effort) [path:/x]",
            "landlock_path_skipped",
        ),
    ],
)
def test_unconfirmed_enforcement_deletes_sandbox(logs: str, reason: str) -> None:
    cli = FakeCli(healthy(logs=logs))
    with pytest.raises(EnforcementUnverifiedError) as exc:
        driver(cli).provision(spec())
    assert exc.value.reason == reason
    assert cli.commands()[-1] == ["openshell", "sandbox", "delete", "prooflayer-01234567"]


def test_create_failure_is_unavailable_and_cleans_up() -> None:
    def handler(argv, input):
        if argv[1:3] == ["sandbox", "create"]:
            return CommandResult(1, b"", b"image not found")
        return healthy()(argv, input)

    cli = FakeCli(handler)
    with pytest.raises(SandboxUnavailableError, match="sandbox_create_failed"):
        driver(cli).provision(spec())
    assert cli.commands()[-1][1:3] == ["sandbox", "delete"]


def test_provision_refuses_when_runtime_unavailable() -> None:
    cli = FakeCli(lambda a, i: CommandResult(None, b"", b"cli_not_found"))
    with pytest.raises(SandboxUnavailableError, match="cli_not_found"):
        driver(cli).provision(spec())
    assert not any(c[1:3] == ["sandbox", "create"] for c in cli.commands())


# --- tool execution ---------------------------------------------------------


def exec_cmd(argv: list[str]) -> list[str]:
    return argv[argv.index("--") + 1 :]


def test_read_file_uses_bounded_head_without_shell() -> None:
    cli = FakeCli(healthy(exec_result=lambda a, i: ok("contents")))
    session = driver(cli).provision(spec())
    result = session.read_file("src/auth.py")
    argv = cli.commands()[-1]
    assert argv[:6] == [
        "openshell",
        "sandbox",
        "exec",
        "-n",
        "prooflayer-01234567",
        "--no-login-shell",
    ]
    assert exec_cmd(argv) == ["head", "-c", "1000", "--", "/sandbox/repo/src/auth.py"]
    assert result.outcome is ToolOutcome.OK
    assert result.simulated is False
    assert result.observation == "contents"


def test_landlock_permission_denied_is_an_enforced_denial() -> None:
    denied = CommandResult(
        1,
        b"",
        b"head: cannot open '/sandbox/repo/.env.production' for reading: Permission denied\n",
    )
    cli = FakeCli(healthy(exec_result=lambda a, i: denied))
    result = driver(cli).provision(spec()).read_file(".env.production")
    assert result.outcome is ToolOutcome.DENIED
    assert result.denial.enforced is True
    assert result.denial.enforcement_point == "landlock"
    assert result.denial.source == "exec_status"
    assert result.denial.target == ".env.production"


def test_write_file_sends_content_on_stdin() -> None:
    cli = FakeCli(healthy(exec_result=lambda a, i: ok()))
    content = 'x = "$(rm -rf /)"\n'
    driver(cli).provision(spec()).write_file("src/auth.py", content)
    argv, stdin, _ = cli.calls[-1]
    assert exec_cmd(argv) == ["dd", "of=/sandbox/repo/src/auth.py", "status=none"]
    assert stdin == content.encode()
    assert content not in " ".join(argv)


def test_run_check_uses_fixed_pytest_argv_env_and_timeout() -> None:
    cli = FakeCli(healthy(exec_result=lambda a, i: CommandResult(1, b"1 failed", b"")))
    result = driver(cli).provision(spec()).run_check("pytest-smoke", 42.0)
    argv, _, timeout = cli.calls[-1]
    assert exec_cmd(argv) == [
        "python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "/sandbox/repo/tests/test_smoke.py",
    ]
    assert argv[argv.index("--env") + 1] == "PYTHONDONTWRITEBYTECODE=1"
    assert timeout == 42.0
    assert result.outcome is ToolOutcome.ERROR
    assert result.exit_code == 1


def test_run_check_timeout() -> None:
    cli = FakeCli(healthy(exec_result=lambda a, i: CommandResult(None, b"", b"", timed_out=True)))
    assert driver(cli).provision(spec()).run_check("pytest-all", 1).outcome is ToolOutcome.TIMEOUT


# --- OCSF evidence ----------------------------------------------------------


def test_parse_ocsf_denials_from_documented_lines() -> None:
    found = parse_ocsf_denials(
        "\n".join([LANDLOCK_OK, NET_DENY, HTTP_DENY, "noise"]), step_action="run_check"
    )
    assert [d.target for _, d in found] == ["httpbin.org:443", "https://api.github.com/user/repos"]
    assert [d.enforcement_point for _, d in found] == ["opa", "l7"]
    assert [d.rule for _, d in found] == ["-", "github_api"]
    assert all(d.source == "ocsf_log" and d.enforced for _, d in found)


def test_drain_denials_reports_each_log_line_once() -> None:
    logs = {"text": LANDLOCK_OK}

    def handler(argv, input):
        if argv[1] == "logs":
            return ok(logs["text"])
        return healthy()(argv, input)

    session = driver(FakeCli(handler)).provision(spec())
    assert session.drain_denials() == []
    logs["text"] = LANDLOCK_OK + NET_DENY
    first = session.drain_denials()
    assert [d.target for d in first] == ["httpbin.org:443"]
    assert session.drain_denials() == []


def test_release_deletes_sandbox() -> None:
    cli = FakeCli(healthy())
    driver(cli).provision(spec()).release()
    assert cli.commands()[-1] == ["openshell", "sandbox", "delete", "prooflayer-01234567"]
