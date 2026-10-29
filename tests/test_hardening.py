"""HTTP hardening: security headers on every response and the request body cap."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from prooflayer_api.hardening import MAX_REQUEST_BODY_BYTES


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
