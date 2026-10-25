"""DockerVerifierDriver: command construction (always) and real containers (opt-in).

The real tests need Docker and ``make verifier-image``; they run with
``RUN_DOCKER_VERIFIER=1`` (CI job ``verifier``). They assert *real* pytest exit
codes for each fixture and that the container really has no network, a
read-only root filesystem and a non-root identity.
"""

from __future__ import annotations

import io
import os
import tarfile

import pytest

from prooflayer_api.ai.scripted import SCRIPTED_CHALLENGES, SCRIPTS
from prooflayer_api.enums import CheckOutcome, TemplateId
from prooflayer_api.sandbox.openshell import CommandResult
from prooflayer_api.services.fixtures import get_fixture
from prooflayer_api.verifier.base import VerifierUnavailableError
from prooflayer_api.verifier.challenge import CHALLENGE_TEST_PATH, validate_test_source
from prooflayer_api.verifier.checks import pytest_outcome
from prooflayer_api.verifier.docker import DockerVerifierDriver
from prooflayer_api.verifier.snapshot import baseline_files, verification_tree

IMAGE_ID = "sha256:" + "cd" * 32


class FakeDocker:
    def __init__(self, *, version_rc=0, inspect_out=IMAGE_ID, run_result=None) -> None:
        self.version_rc = version_rc
        self.inspect_out = inspect_out
        self.run_result = run_result or CommandResult(0, b"1 passed", b"")
        self.calls: list[tuple[list[str], bytes | None, float]] = []

    def __call__(self, argv, *, input=None, timeout):
        argv = list(argv)
        self.calls.append((argv, input, timeout))
        if argv[1] == "version":
            if self.version_rc is None:
                return CommandResult(None, b"", b"cli_not_found")
            return CommandResult(self.version_rc, b"29.0.1\n", b"")
        if argv[1:3] == ["image", "inspect"]:
            return CommandResult(0 if self.inspect_out else 1, self.inspect_out.encode(), b"")
        if argv[1] == "run":
            return self.run_result
        return CommandResult(0, b"", b"")


def driver(fake: FakeDocker, **kwargs) -> DockerVerifierDriver:
    return DockerVerifierDriver(runner=fake, **kwargs)


@pytest.mark.parametrize(
    ("fake", "reason"),
    [
        (FakeDocker(version_rc=None), "cli_not_found"),
        (FakeDocker(version_rc=1), "daemon_unreachable"),
        (FakeDocker(inspect_out=""), "verifier_image_missing"),
        (FakeDocker(inspect_out="not-an-id"), "verifier_image_missing"),
    ],
)
def test_probe_reports_why_the_verifier_is_unavailable(fake, reason) -> None:
    status = driver(fake).probe()
    assert (status.available, status.reason) == (False, reason)
    with pytest.raises(VerifierUnavailableError, match=reason):
        driver(fake).identity()


def test_pinned_image_id_mismatch_is_unavailable() -> None:
    status = driver(FakeDocker(), expected_image_id="sha256:" + "00" * 32).probe()
    assert status.reason == "verifier_image_mismatch"


def test_run_is_isolated_and_pinned_by_image_id() -> None:
    fake = FakeDocker()
    files = {"tests/test_a.py": b"def test_a():\n    pass\n"}
    execution = driver(fake, memory="256m", cpus="0.5", pids_limit=64).run_pytest(
        files, ("tests",), 30
    )
    argv, stdin, timeout = fake.calls[-1]
    assert argv[:4] == ["docker", "run", "--rm", "-i"]
    pairs = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    assert pairs["--network"] == "none"
    assert pairs["--cap-drop"] == "ALL"
    assert pairs["--security-opt"] == "no-new-privileges"
    assert pairs["--user"] == "10002:10002"
    assert pairs["--memory"] == pairs["--memory-swap"] == "256m"
    assert pairs["--cpus"] == "0.5"
    assert pairs["--pids-limit"] == "64"
    assert "--read-only" in argv
    assert argv[-2:] == [IMAGE_ID, "tests"]
    # No host directory, socket or privilege ever reaches the container.
    for forbidden in ("-v", "--volume", "--mount", "--privileged", "--network=host"):
        assert forbidden not in argv
    assert not any("docker.sock" in a for a in argv)
    assert timeout == 30
    with tarfile.open(fileobj=io.BytesIO(stdin)) as archive:
        assert archive.extractfile("tests/test_a.py").read() == files["tests/test_a.py"]
    assert (execution.exit_code, execution.output_bytes) == (0, len(b"1 passed"))


def test_timeout_kills_the_container_and_is_not_a_result() -> None:
    fake = FakeDocker(run_result=CommandResult(None, b"", b"", timed_out=True))
    execution = driver(fake).run_pytest({"tests/test_a.py": b""}, ("tests",), 1)
    name = fake.calls[-2][0][fake.calls[-2][0].index("--name") + 1]
    assert fake.calls[-1][0] == ["docker", "rm", "-f", name]
    assert pytest_outcome(execution) == (CheckOutcome.INCONCLUSIVE, "timeout")


@pytest.mark.parametrize("code", [125, 126, 127])
def test_docker_engine_errors_are_not_test_results(code) -> None:
    fake = FakeDocker(run_result=CommandResult(code, b"", b"boom"))
    execution = driver(fake).run_pytest({"tests/test_a.py": b""}, ("tests",), 1)
    assert execution.exit_code is None
    assert pytest_outcome(execution) == (CheckOutcome.INCONCLUSIVE, "container_failed")


# --- real Docker (opt-in) ----------------------------------------------------

real = pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_VERIFIER") != "1",
    reason="set RUN_DOCKER_VERIFIER=1 (needs Docker and `make verifier-image`)",
)
_REAL_ENV = {k: os.environ.get(k) for k in ("DOCKER_BIN", "VERIFIER_IMAGE")}


@pytest.fixture
def docker_verifier() -> DockerVerifierDriver:
    verifier = DockerVerifierDriver(
        bin=_REAL_ENV["DOCKER_BIN"] or "docker",
        image=_REAL_ENV["VERIFIER_IMAGE"] or "prooflayer-verifier:0.1.0",
    )
    status = verifier.probe()
    assert status.available, status.reason  # opted in: unavailability is a failure
    return verifier


def scripted_agent_files(template: TemplateId) -> dict[str, bytes]:
    return {
        step["path"]: step["content"].encode()
        for step in SCRIPTS[template]
        if step["action"] == "write_file"
    }


def tree_after_agent(template: TemplateId) -> dict[str, bytes]:
    fixture = get_fixture(template)
    return verification_tree(
        baseline_files(template), scripted_agent_files(template), fixture.allowed_paths
    )


@real
@pytest.mark.parametrize(
    ("template", "baseline_exit", "after_agent_exit"),
    [
        (TemplateId.SUCCESS_VALIDATION, 1, 0),
        (TemplateId.FALSE_SUCCESS_AUTH, 1, 1),
        (TemplateId.DENIED_SECRET_READ, 1, 0),
    ],
)
def test_real_pinned_suites_give_expected_exit_codes(
    docker_verifier, template, baseline_exit, after_agent_exit
) -> None:
    before = docker_verifier.run_pytest(baseline_files(template), ("tests",), 120)
    after = docker_verifier.run_pytest(tree_after_agent(template), ("tests",), 120)
    assert before.exit_code == baseline_exit, before.excerpt.decode()
    assert after.exit_code == after_agent_exit, after.excerpt.decode()


@real
@pytest.mark.parametrize(
    ("template", "outcome"),
    [
        (TemplateId.SUCCESS_VALIDATION, CheckOutcome.PASS),
        (TemplateId.FALSE_SUCCESS_AUTH, CheckOutcome.FAIL),
        (TemplateId.DENIED_SECRET_READ, CheckOutcome.PASS),
    ],
)
def test_real_scripted_challenges(docker_verifier, template, outcome) -> None:
    validated = validate_test_source(SCRIPTED_CHALLENGES[template]["test_source"])
    tree = {**tree_after_agent(template), CHALLENGE_TEST_PATH: validated.source.encode()}
    execution = docker_verifier.run_pytest(tree, (CHALLENGE_TEST_PATH,), 120)
    assert pytest_outcome(execution)[0] is outcome, execution.excerpt.decode()


# Deliberately NOT passed through the challenge validator: this probes the
# container boundary itself, which must hold even if validation is bypassed.
ISOLATION_PROBE = b"""
import os
import socket

import pytest


def test_no_network() -> None:
    with pytest.raises(OSError):
        socket.create_connection(("1.1.1.1", 53), timeout=3)


def test_root_filesystem_is_read_only() -> None:
    with pytest.raises(OSError):
        open("/opt/prooflayer/run_check.py", "a")


def test_runs_as_unprivileged_verifier_user() -> None:
    assert os.getuid() == 10002
    assert os.getgid() == 10002


def test_no_secrets_or_agent_sandbox_paths() -> None:
    assert not os.path.exists("/sandbox")
    assert not os.path.exists("/var/run/docker.sock")
    assert not any(k.startswith(("NEBIUS", "TAVILY")) for k in os.environ)
"""


@real
def test_real_container_has_no_network_read_only_root_and_non_root_user(docker_verifier) -> None:
    tree = {"tests/test_isolation.py": ISOLATION_PROBE}
    execution = docker_verifier.run_pytest(tree, ("tests/test_isolation.py",), 120)
    assert execution.exit_code == 0, execution.excerpt.decode()


@real
def test_real_harness_rejects_traversal_targets(docker_verifier) -> None:
    execution = docker_verifier.run_pytest({"tests/test_a.py": b""}, ("../etc",), 60)
    assert execution.exit_code == 101
    assert pytest_outcome(execution)[1] == "verifier_harness_error"
