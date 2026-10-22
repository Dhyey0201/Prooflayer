from __future__ import annotations

import copy

import pytest
import yaml

from prooflayer_api.enums import TemplateId
from prooflayer_api.sandbox.base import SandboxSpec, ToolOutcome
from prooflayer_api.sandbox.mock import MockSandboxDriver
from prooflayer_api.sandbox.policy import (
    REPO_DIR,
    SECRETS_DIR,
    PolicyError,
    build_agent_policy,
    policy_sha256,
    render_policy,
    validate_policy,
)
from prooflayer_api.sandbox.workspaces import workspace_files, workspace_listing
from prooflayer_api.services.fixtures import FIXTURES, get_fixture


@pytest.mark.parametrize("template", list(TemplateId))
def test_generated_policy_is_least_privilege(template: TemplateId) -> None:
    fixture = get_fixture(template)
    policy = build_agent_policy(fixture)
    fs = policy["filesystem_policy"]

    assert policy["version"] == 1
    assert fs["include_workdir"] is False
    assert REPO_DIR in fs["read_only"]
    assert REPO_DIR not in fs["read_write"]
    assert [p for p in fs["read_write"] if p.startswith(REPO_DIR)] == [
        f"{REPO_DIR}/{p}" for p in fixture.allowed_paths
    ]
    assert not any(p.startswith(SECRETS_DIR) for p in fs["read_only"] + fs["read_write"])
    assert "network_policies" not in policy  # OpenShell default: all egress denied
    assert policy["landlock"] == {"compatibility": "hard_requirement"}
    assert policy["process"]["run_as_user"] != "0"


def test_rendered_policy_round_trips_and_hash_is_stable() -> None:
    fixture = get_fixture(TemplateId.DENIED_SECRET_READ)
    rendered = render_policy(build_agent_policy(fixture))
    assert yaml.safe_load(rendered) == build_agent_policy(fixture)
    assert policy_sha256(rendered) == policy_sha256(render_policy(build_agent_policy(fixture)))
    assert len(policy_sha256(rendered)) == 64


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p["filesystem_policy"]["read_only"].append(SECRETS_DIR), "secrets"),
        (lambda p: p["filesystem_policy"]["read_only"].append("/sandbox"), "secrets"),
        (lambda p: p["filesystem_policy"]["read_write"].append("/"), "secrets"),
        (lambda p: p["filesystem_policy"]["read_only"].append("relative/path"), "invalid"),
        (lambda p: p["filesystem_policy"]["read_only"].append("/a/../sandbox"), "invalid"),
        (lambda p: p.__setitem__("network_policies", {"any": {}}), "network"),
        (lambda p: p["filesystem_policy"].__setitem__("include_workdir", True), "workdir"),
        (lambda p: p["landlock"].__setitem__("compatibility", "best_effort"), "landlock"),
    ],
)
def test_policy_validation_rejects_unsafe_changes(mutate, message: str) -> None:
    policy = copy.deepcopy(build_agent_policy(get_fixture(TemplateId.SUCCESS_VALIDATION)))
    mutate(policy)
    with pytest.raises(PolicyError, match=message):
        validate_policy(policy)


def test_workspaces_exist_and_never_contain_denied_files() -> None:
    for fixture in FIXTURES.values():
        files = workspace_files(fixture.id)
        assert any(path.startswith("tests/") for path in files)
        for allowed in fixture.allowed_paths:
            assert allowed in files
        for denied in fixture.read_denied_paths:
            assert denied not in files  # generated in the image, never committed
            assert denied in workspace_listing(fixture.id, fixture.read_denied_paths)


def _session(template: TemplateId):
    fixture = get_fixture(template)
    return MockSandboxDriver().provision(
        SandboxSpec("r", fixture, timeout_seconds=10, max_output_bytes=50)
    )


def test_mock_sandbox_models_policy_but_never_claims_enforcement() -> None:
    session = _session(TemplateId.DENIED_SECRET_READ)
    assert session.info.enforced is False
    assert session.info.driver == "mock"

    denied = session.read_file(".env.production")
    assert denied.outcome is ToolOutcome.DENIED
    assert denied.denial.enforced is False
    assert denied.denial.source == "mock_policy"

    write_outside = session.write_file("README.md", "x")
    assert write_outside.outcome is ToolOutcome.DENIED
    assert write_outside.denial.rule == "allowed_paths"

    assert session.write_file("src/auth.py", "x = 1\n").outcome is ToolOutcome.OK
    assert session.file_content("src/auth.py") == "x = 1\n"
    assert session.read_file("missing.py").outcome is ToolOutcome.ERROR


def test_mock_read_is_bounded_and_hashed() -> None:
    session = _session(TemplateId.SUCCESS_VALIDATION)
    result = session.read_file("README.md")
    assert result.output_bytes == 50
    assert result.truncated is True
    assert len(result.output_sha256) == 64


def test_mock_checks_are_simulated_never_passed() -> None:
    result = _session(TemplateId.FALSE_SUCCESS_AUTH).run_check("pytest-all", 5)
    assert result.simulated is True
    assert result.exit_code is None
    assert "not executed" in result.observation
