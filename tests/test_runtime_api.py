"""Capabilities and live-mode gating reflect the real runtime, never a default of 'secure'."""

from __future__ import annotations

from fastapi.testclient import TestClient

from prooflayer_api.main import create_app
from prooflayer_api.sandbox.openshell import CommandResult, OpenShellDriver
from prooflayer_api.services.runtime import Runtime, default_transport_factory
from tests.conftest import FAKE_NEBIUS_KEY


def healthy_cli(argv, *, input=None, timeout):
    if argv[1] == "--version":
        return CommandResult(0, b"openshell 0.1.5\n", b"")
    return CommandResult(0, b"", b"")


def app_with(make_settings, migrated_db_url, runner=healthy_cli, **values):
    settings = make_settings(DATABASE_URL=migrated_db_url, SANDBOX_DRIVER="openshell", **values)
    runtime = Runtime(
        settings=settings,
        driver=OpenShellDriver(runner=runner),
        transport_factory=default_transport_factory(settings),
    )
    return create_app(settings, runtime)


def live(api: TestClient):
    return api.post("/api/v1/runs", json={"template_id": "success-validation", "mode": "live"})


def test_openshell_configured_but_missing_is_reported_unavailable(make_settings) -> None:
    settings = make_settings(SANDBOX_DRIVER="openshell", OPENSHELL_BIN="/nonexistent/openshell")
    body = TestClient(create_app(settings)).get("/api/v1/capabilities").json()
    assert body["openshell_available"] is False
    assert body["sandbox_enforced"] is False


def test_reachable_openshell_is_reported_enforcing(make_settings, migrated_db_url) -> None:
    with TestClient(app_with(make_settings, migrated_db_url)) as api:
        body = api.get("/api/v1/capabilities").json()
    assert body["openshell_available"] is True
    assert body["sandbox_enforced"] is True
    assert body["independent_verifier_available"] is False


def test_live_mode_accepted_only_with_live_model_and_enforcing_sandbox(
    make_settings, migrated_db_url
) -> None:
    keyed = {"NEBIUS_API_KEY": FAKE_NEBIUS_KEY, "PROOFLAYER_MOCK_MODE": False}
    with TestClient(app_with(make_settings, migrated_db_url, **keyed)) as api:
        response = live(api)
        assert response.status_code == 201
        assert response.json()["mode"] == "live"
        assert FAKE_NEBIUS_KEY not in response.text


def test_live_mode_refused_without_enforcing_sandbox(make_settings, migrated_db_url) -> None:
    def gateway_down(argv, *, input=None, timeout):
        if argv[1] == "--version":
            return CommandResult(0, b"openshell 0.1.5\n", b"")
        return CommandResult(1, b"", b"")

    keyed = {"NEBIUS_API_KEY": FAKE_NEBIUS_KEY, "PROOFLAYER_MOCK_MODE": False}
    with TestClient(app_with(make_settings, migrated_db_url, gateway_down, **keyed)) as api:
        assert live(api).status_code == 422
        assert api.get("/api/v1/runs").json() == []


def test_live_mode_refused_without_live_model(make_settings, migrated_db_url) -> None:
    with TestClient(app_with(make_settings, migrated_db_url)) as api:
        assert live(api).status_code == 422


def test_replay_mode_is_not_available(make_settings, migrated_db_url) -> None:
    with TestClient(app_with(make_settings, migrated_db_url)) as api:
        response = api.post(
            "/api/v1/runs", json={"template_id": "success-validation", "mode": "replay"}
        )
        assert response.status_code == 422
