from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prooflayer_api.enums import TemplateId
from prooflayer_api.evidence.hashchain import GENESIS_HASH, verify_chain
from prooflayer_api.main import DatabaseNotMigratedError, create_app

ROOT = Path(__file__).resolve().parents[1]


def _create(api: TestClient, template_id: str = "false-success-auth", **kwargs):
    return api.post("/api/v1/runs", json={"template_id": template_id, "mode": "fixture"}, **kwargs)


# --- templates -------------------------------------------------------------


def test_templates_list_trusted_registry(api: TestClient) -> None:
    response = api.get("/api/v1/templates")
    assert response.status_code == 200
    templates = response.json()
    assert [t["id"] for t in templates] == [t.value for t in TemplateId]
    for template in templates:
        assert template["allowed_paths"]
        assert template["required_checks"]
        assert ".env.production" in template["read_denied_paths"]
        # Pinned by tree digest; the verifier refuses a baseline that differs.
        assert len(template["repo_sha"]) == 64


def test_template_expected_verdicts_match_benchmark_manifest(api: TestClient) -> None:
    manifest = json.loads((ROOT / "benchmarks" / "fixture_manifest.json").read_text())
    ground_truth = {f["id"]: f["ground_truth"] for f in manifest["fixtures"]}
    served = {t["id"]: t["expected_verdict"] for t in api.get("/api/v1/templates").json()}
    assert served == ground_truth


# --- create / read / list --------------------------------------------------


def test_create_run_returns_queued_run_without_verdict(api: TestClient) -> None:
    response = _create(api)
    assert response.status_code == 201
    run = response.json()
    uuid.UUID(run["id"])
    assert run["template_id"] == "false-success-auth"
    assert run["status"] == "queued"
    assert run["mode"] == "fixture"
    assert run["verdict"] is None
    assert run["agent_claim"] is None
    assert run["created_at"].endswith("Z")


def test_created_run_has_valid_ordered_event_chain(api: TestClient) -> None:
    run_id = _create(api).json()["id"]
    events = api.get(f"/api/v1/runs/{run_id}/events").json()
    assert [(e["seq"], e["event_type"]) for e in events] == [
        (1, "run.created"),
        (2, "run.status_changed"),
    ]
    assert events[0]["previous_hash"] == GENESIS_HASH
    assert events[0]["safe_payload"] == {
        "template_id": "false-success-auth",
        "mode": "fixture",
        "policy_version": "0.1.0",
    }
    assert events[1]["safe_payload"] == {
        "from_status": "created",
        "to_status": "queued",
        "reason": "accepted",
    }
    assert all(e["actor"] == "api" for e in events)
    assert verify_chain(events).valid is True


def test_events_after_seq(api: TestClient) -> None:
    run_id = _create(api).json()["id"]
    events = api.get(f"/api/v1/runs/{run_id}/events", params={"after_seq": 1}).json()
    assert [e["seq"] for e in events] == [2]
    assert api.get(f"/api/v1/runs/{run_id}/events", params={"after_seq": -1}).status_code == 422


def test_get_run_roundtrip(api: TestClient) -> None:
    created = _create(api).json()
    assert api.get(f"/api/v1/runs/{created['id']}").json() == created


def test_list_runs_newest_first(api: TestClient) -> None:
    first = _create(api, "success-validation").json()["id"]
    second = _create(api, "denied-secret-read").json()["id"]
    ids = [r["id"] for r in api.get("/api/v1/runs").json()]
    assert ids == [second, first]
    assert len(api.get("/api/v1/runs", params={"limit": 1}).json()) == 1
    assert api.get("/api/v1/runs", params={"limit": 0}).status_code == 422


def test_unknown_run_is_404(api: TestClient) -> None:
    missing = uuid.uuid4()
    for path in (f"/api/v1/runs/{missing}", f"/api/v1/runs/{missing}/events"):
        response = api.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    assert api.post(f"/api/v1/runs/{missing}/cancel").status_code == 404


def test_malformed_run_id_is_422(api: TestClient) -> None:
    assert api.get("/api/v1/runs/not-a-uuid").status_code == 422


# --- validation ------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"template_id": "rm -rf /", "mode": "fixture"},
        {"template_id": "../etc/passwd"},
        {"mode": "fixture"},
        {"template_id": "success-validation", "mode": "replay"},
        {"template_id": "success-validation", "command": ["sh", "-c", "id"]},
        {"template_id": "success-validation", "repo_url": "https://example.com/x.git"},
    ],
)
def test_invalid_scenario_or_settings_is_422(api: TestClient, body: dict) -> None:
    response = api.post("/api/v1/runs", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert api.get("/api/v1/runs").json() == []


def test_live_mode_is_refused_until_a_live_runtime_exists(api: TestClient) -> None:
    response = api.post("/api/v1/runs", json={"template_id": "success-validation", "mode": "live"})
    assert response.status_code == 422
    assert "enforcing OpenShell sandbox" in response.json()["error"]["message"]
    assert api.get("/api/v1/runs").json() == []


def test_mode_defaults_to_fixture(api: TestClient) -> None:
    response = api.post("/api/v1/runs", json={"template_id": "success-validation"})
    assert response.status_code == 201
    assert response.json()["mode"] == "fixture"


# --- idempotency -----------------------------------------------------------


def test_idempotency_key_replays_same_run(api: TestClient) -> None:
    headers = {"Idempotency-Key": "demo-key-0001"}
    first = _create(api, headers=headers)
    second = _create(api, headers=headers)
    assert first.status_code == second.status_code == 201
    assert second.headers["Idempotent-Replayed"] == "true"
    assert "Idempotent-Replayed" not in first.headers
    assert first.json()["id"] == second.json()["id"]
    assert len(api.get("/api/v1/runs").json()) == 1
    assert len(api.get(f"/api/v1/runs/{first.json()['id']}/events").json()) == 2


def test_idempotency_key_reuse_with_different_body_is_409(api: TestClient) -> None:
    headers = {"Idempotency-Key": "demo-key-0002"}
    assert _create(api, "success-validation", headers=headers).status_code == 201
    response = _create(api, "denied-secret-read", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize("key", ["short", "has space here", "x" * 129, "semi;colon-key"])
def test_malformed_idempotency_key_is_422(api: TestClient, key: str) -> None:
    assert _create(api, headers={"Idempotency-Key": key}).status_code == 422


# --- limits ----------------------------------------------------------------


def test_pending_run_cap_returns_429(make_settings, migrated_db_url: str) -> None:
    app = create_app(make_settings(DATABASE_URL=migrated_db_url, PROOFLAYER_MAX_PENDING_RUNS=2))
    with TestClient(app) as api:
        assert _create(api).status_code == 201
        second = _create(api).json()["id"]
        response = _create(api)
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "rate_limited"
        # Canceling frees a slot.
        assert api.post(f"/api/v1/runs/{second}/cancel").status_code == 202
        assert _create(api).status_code == 201


# --- cancel ----------------------------------------------------------------


def test_cancel_records_transition_and_is_idempotent(api: TestClient) -> None:
    run_id = _create(api).json()["id"]
    first = api.post(f"/api/v1/runs/{run_id}/cancel")
    assert first.status_code == 202
    assert first.json()["status"] == "canceled"
    assert first.json()["verdict"] is None

    again = api.post(f"/api/v1/runs/{run_id}/cancel")
    assert again.status_code == 202
    events = api.get(f"/api/v1/runs/{run_id}/events").json()
    assert [e["safe_payload"].get("to_status") for e in events] == [None, "queued", "canceled"]
    assert events[-1]["safe_payload"]["reason"] == "user_requested"
    assert verify_chain(events).valid is True


# --- startup ---------------------------------------------------------------


def test_unmigrated_database_fails_fast(make_settings, db_url: str) -> None:
    app = create_app(make_settings(DATABASE_URL=db_url))
    with pytest.raises(DatabaseNotMigratedError, match="make migrate"), TestClient(app):
        pass


def test_cors_preflight_allows_idempotency_key(api: TestClient) -> None:
    response = api.options(
        "/api/v1/runs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key",
        },
    )
    assert response.status_code == 200
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()
