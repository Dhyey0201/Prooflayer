"""HTTP hardening: security headers on every response and the request body cap."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from prooflayer_api.hardening import MAX_REQUEST_BODY_BYTES
from prooflayer_api.main import create_app


def test_json_responses_carry_security_headers(client: TestClient) -> None:
    for response in (client.get("/api/v1/health"), client.get("/api/v1/nope")):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["content-security-policy"] == (
            "default-src 'none'; frame-ancestors 'none'"
        )
        assert response.headers["cache-control"] == "no-store"


def test_docs_page_keeps_its_scripts_but_still_gets_base_headers(client: TestClient) -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def _assert_payload_too_large(response) -> None:
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "payload_too_large"
    assert error["request_id"] == response.headers["x-request-id"]


def test_declared_oversized_body_is_refused_before_routing(client: TestClient) -> None:
    body = json.dumps({"template_id": "success-validation", "pad": "x" * MAX_REQUEST_BODY_BYTES})
    _assert_payload_too_large(
        client.post("/api/v1/runs", content=body, headers={"Content-Type": "application/json"})
    )


def test_streamed_oversized_body_without_length_is_refused(client: TestClient) -> None:
    def chunks():
        for _ in range(5):
            yield b"x" * (MAX_REQUEST_BODY_BYTES // 4)

    _assert_payload_too_large(
        client.post("/api/v1/runs", content=chunks(), headers={"Content-Type": "application/json"})
    )


def test_oversized_413_is_readable_cross_origin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/runs",
        content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
        headers={"Content-Type": "application/json", "Origin": "http://localhost:3000"},
    )
    _assert_payload_too_large(response)
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_small_bodies_still_reach_the_route(api: TestClient) -> None:
    response = api.post("/api/v1/runs", json={"template_id": "success-validation"})
    assert response.status_code == 201
    assert response.json()["template_id"] == "success-validation"


def test_read_only_deployment_refuses_every_write(make_settings, migrated_db_url: str) -> None:
    settings = make_settings(
        DATABASE_URL=migrated_db_url, PROOFLAYER_READ_ONLY=True, PROOFLAYER_WORKER_ENABLED=True
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert app.state.worker is None
        for method, path in (
            ("POST", "/api/v1/runs"),
            ("POST", f"/api/v1/runs/{uuid.uuid4()}/cancel"),
            ("POST", f"/api/v1/runs/{uuid.uuid4()}/challenge"),
            ("PUT", "/api/v1/runs"),
            ("DELETE", "/api/v1/runs"),
        ):
            response = client.request(
                method,
                path,
                json={"template_id": "success-validation"},
                headers={"Origin": "http://localhost:3000"},
            )
            assert response.status_code == 403, (method, path)
            error = response.json()["error"]
            assert error["code"] == "read_only"
            assert error["request_id"] == response.headers["x-request-id"]
            assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert client.get("/api/v1/runs").json() == []
        assert client.get("/api/v1/capabilities").json()["read_only"] is True


def test_writes_are_allowed_when_not_read_only(api: TestClient) -> None:
    assert api.get("/api/v1/capabilities").json()["read_only"] is False
    assert api.post("/api/v1/runs", json={"template_id": "success-validation"}).status_code == 201
