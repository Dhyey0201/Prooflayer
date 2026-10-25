"""Opt-in live checks: real Nebius Token Factory and a real OpenShell sandbox.

Skipped unless ``RUN_LIVE_INTEGRATION=1`` (never in CI). The OpenShell test
is the one that certifies the policy: it FAILS if the read-denied file can be
read or if no denial is observed (policy/README.md, step 4).

    RUN_LIVE_INTEGRATION=1 NEBIUS_API_KEY=... pytest -q tests/test_live_integration.py
    RUN_LIVE_INTEGRATION=1 make sandbox-image   # then the OpenShell test
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from prooflayer_api.ai.client import ChatMessage
from prooflayer_api.config import Settings
from prooflayer_api.enums import TemplateId
from prooflayer_api.sandbox.base import SandboxSpec, ToolOutcome
from prooflayer_api.sandbox.openshell import OpenShellDriver
from prooflayer_api.services.fixtures import get_fixture

LIVE = os.environ.get("RUN_LIVE_INTEGRATION") == "1"
pytestmark = pytest.mark.skipif(not LIVE, reason="set RUN_LIVE_INTEGRATION=1 to run live checks")


@pytest.fixture
def live_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    # conftest clears these; restore the real values captured at import time.
    for name, value in _ORIGINAL_ENV.items():
        if value is not None:
            monkeypatch.setenv(name, value)
    return Settings()


_ORIGINAL_ENV = {
    name: os.environ.get(name)
    for name in (
        "NEBIUS_API_KEY",
        "NEBIUS_BASE_URL",
        "NEBIUS_MODEL_ID",
        "OPENSHELL_BIN",
        "PROOFLAYER_SANDBOX_IMAGE",
    )
}


def test_nebius_model_is_listed_and_answers_json(live_settings: Settings) -> None:
    if not live_settings.nebius_configured:
        pytest.skip("NEBIUS_API_KEY not set")
    from prooflayer_api.ai.nebius import NebiusTransport

    transport = NebiusTransport(live_settings)
    assert live_settings.nebius_model_id in transport.list_models()
    result = transport.complete(
        [
            ChatMessage("system", 'Reply with exactly {"action": "list_files"}'),
            ChatMessage("user", "Begin."),
        ],
        max_tokens=64,
    )
    assert result.completion_tokens > 0
    assert "list_files" in result.content


def test_nemotron_challenge_proposal_parses_and_validates(live_settings: Settings) -> None:
    """One real proposal; it must satisfy the schema and the static validator."""
    if not live_settings.nebius_configured:
        pytest.skip("NEBIUS_API_KEY not set")
    from prooflayer_api.ai.client import CircuitBreaker, ModelClient, RunBudget
    from prooflayer_api.ai.nebius import NebiusTransport
    from prooflayer_api.verifier.challenge import validate_test_source
    from prooflayer_api.verifier.proposer import propose_challenge

    fixture = get_fixture(TemplateId.FALSE_SUCCESS_AUTH)
    client = ModelClient(
        transport=NebiusTransport(live_settings),
        budget=RunBudget(max_calls=2, max_tokens=8000),
        breaker=CircuitBreaker(),
        max_retries=1,
    )
    workspace = Path(__file__).parents[1] / "apps/api/prooflayer_api/fixture_workspaces"
    source = (workspace / "false-success-auth/src/auth.py").read_text()
    proposal = propose_challenge(
        client, fixture, "Fixed token refresh. All tests passed.", {"src/auth.py": source}
    )
    assert proposal.requirement_id in fixture.required_checks
    assert validate_test_source(proposal.test_source).test_count >= 1


def test_openshell_denies_secret_read_and_out_of_allowlist_write(live_settings: Settings) -> None:
    driver = OpenShellDriver(
        bin=live_settings.openshell_bin,
        image=live_settings.sandbox_image,
        cpu=live_settings.sandbox_cpu,
        memory=live_settings.sandbox_memory,
    )
    status = driver.probe()
    if not status.available:
        pytest.skip(f"OpenShell unavailable: {status.reason}")

    spec = SandboxSpec(uuid.uuid4().hex, get_fixture(TemplateId.DENIED_SECRET_READ), 120, 100_000)
    session = driver.provision(spec)
    try:
        assert session.info.enforced is True

        allowed = session.read_file("src/auth.py")
        assert allowed.outcome is ToolOutcome.OK, allowed.observation
        assert "bearer_header" in allowed.observation

        secret = session.read_file(".env.production")
        assert secret.outcome is ToolOutcome.DENIED, "read-denied file was readable"
        assert "prooflayer-fake-token" not in secret.observation
        assert secret.denial is not None and secret.denial.enforced is True

        outside = session.write_file("README.md", "tampered\n")
        assert outside.outcome is ToolOutcome.DENIED, "write outside allowed_paths succeeded"

        inside = session.write_file("src/auth.py", allowed.observation)
        assert inside.outcome is ToolOutcome.OK, inside.observation

        smoke = session.run_check("pytest-smoke", 60)
        assert smoke.simulated is False
        assert smoke.exit_code == 0, smoke.observation
    finally:
        session.release()
