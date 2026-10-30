from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from prooflayer_api.main import create_app
from tests.conftest import FAKE_NEBIUS_KEY


def test_health_under_api_prefix(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unprefixed_liveness_probe(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_capabilities_boot_without_key_in_mock_mode(client: TestClient) -> None:
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["mock_mode"] is True
    assert body["nebius_configured"] is False
    assert body["live_model_enabled"] is False


def test_capabilities_are_booleans_only(client: TestClient) -> None:
    body = client.get("/api/v1/capabilities").json()
    assert body
    assert all(isinstance(value, bool) for value in body.values())


def test_capabilities_never_claim_sandbox_enforcement(client: TestClient) -> None:
    body = client.get("/api/v1/capabilities").json()
    assert body["openshell_available"] is False
    assert body["sandbox_enforced"] is False
    assert body["unenforced_live_allowed"] is False
    assert body["independent_verifier_available"] is False


def test_capabilities_with_key_reports_flag_but_never_the_key(make_settings) -> None:
    settings = make_settings(
        NEBIUS_API_KEY=FAKE_NEBIUS_KEY, PROOFLAYER_MOCK_MODE=False, TAVILY_API_KEY="tvly-fake"
    )
    client = TestClient(create_app(settings))
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["nebius_configured"] is True
    assert body["live_model_enabled"] is True
    assert body["tavily_enabled"] is True
    assert FAKE_NEBIUS_KEY not in response.text
    assert "tvly-fake" not in response.text


def test_key_not_exposed_in_openapi_or_health(make_settings) -> None:
    client = TestClient(create_app(make_settings(NEBIUS_API_KEY=FAKE_NEBIUS_KEY)))
    for path in ("/health", "/api/v1/health", "/api/v1/capabilities", "/openapi.json"):
        assert FAKE_NEBIUS_KEY not in client.get(path).text


def test_request_id_generated_when_absent(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    uuid.UUID(response.headers["X-Request-ID"])


def test_safe_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc-12345678"})
    assert response.headers["X-Request-ID"] == "trace-abc-12345678"


def test_unsafe_request_id_is_replaced(client: TestClient) -> None:
    hostile = "x" * 10 + "<script>"
    response = client.get("/api/v1/health", headers={"X-Request-ID": hostile})
    assert response.headers["X-Request-ID"] != hostile
    uuid.UUID(response.headers["X-Request-ID"])


def test_cors_allows_configured_web_origin(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_benchmark_report_is_served_as_published(make_settings, tmp_path) -> None:
    report = {"schema_version": "0.1.0", "seed_count": 18, "metrics": {}}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    client = TestClient(create_app(make_settings(PROOFLAYER_BENCHMARK_REPORT=str(path))))
    response = client.get("/api/v1/benchmark")
    assert response.status_code == 200
    assert response.json() == report


def test_missing_or_corrupt_benchmark_report_is_404(make_settings, tmp_path) -> None:
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json")
    for path in (tmp_path / "missing.json", corrupt):
        client = TestClient(create_app(make_settings(PROOFLAYER_BENCHMARK_REPORT=str(path))))
        response = client.get("/api/v1/benchmark")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_default_benchmark_report_is_the_committed_reference_run(make_settings) -> None:
    body = TestClient(create_app(make_settings())).get("/api/v1/benchmark").json()
    assert body["seed_count"] == 18
    assert body["all_expectations_met"] is True
