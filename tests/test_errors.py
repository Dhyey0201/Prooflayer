from __future__ import annotations

from fastapi import Query
from fastapi.testclient import TestClient

from prooflayer_api.enums import ErrorCode
from prooflayer_api.errors import ApiError
from prooflayer_api.main import create_app


def _app_with_probe_routes(make_settings):
    app = create_app(make_settings())

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("internal detail with sk-secret-value")

    @app.get("/conflict")
    def conflict() -> None:
        raise ApiError(409, ErrorCode.CONFLICT, "Run is not challengeable yet")

    @app.get("/needs-int")
    def needs_int(limit: int = Query(...)) -> dict:
        return {"limit": limit}

    return app


def test_unknown_route_returns_typed_404(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist", headers={"X-Request-ID": "req-404-abcdef"})
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found", "request_id": "req-404-abcdef"}
    }


def test_unhandled_exception_is_generic_500_with_request_id(make_settings) -> None:
    client = TestClient(_app_with_probe_routes(make_settings))
    response = client.get("/boom", headers={"X-Request-ID": "req-500-abcdef"})
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "req-500-abcdef"
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "request_id": "req-500-abcdef",
        }
    }
    assert "sk-secret-value" not in response.text


def test_api_error_is_typed(make_settings) -> None:
    client = TestClient(_app_with_probe_routes(make_settings))
    response = client.get("/conflict")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_validation_error_does_not_echo_input(make_settings) -> None:
    client = TestClient(_app_with_probe_routes(make_settings))
    response = client.get("/needs-int", params={"limit": "sk-secret-value"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "query.limit" in body["error"]["message"]
    assert "sk-secret-value" not in response.text
