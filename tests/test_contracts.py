"""The API must agree with contracts/openapi.yaml, which is canonical."""

from __future__ import annotations

from fastapi.testclient import TestClient

from prooflayer_api.enums import (
    Actor,
    ErrorCode,
    EventType,
    RunMode,
    RunStatus,
    TemplateId,
    Verdict,
)
from prooflayer_api.main import API_PREFIX
from prooflayer_contracts import api_prefix, component_enum, load_openapi, load_schemas


def test_api_prefix_matches_contract_server() -> None:
    assert api_prefix() == API_PREFIX


def test_run_status_matches_contract() -> None:
    assert [s.value for s in RunStatus] == component_enum("Run", "status")


def test_run_mode_matches_contract() -> None:
    assert [m.value for m in RunMode] == component_enum("Run", "mode")


def test_template_ids_match_contract() -> None:
    assert [t.value for t in TemplateId] == component_enum("RunCreate", "template_id")


def test_verdicts_match_contract() -> None:
    contract = [v for v in component_enum("Run", "verdict") if v is not None]
    assert [v.value for v in Verdict] == contract
    certificate = load_openapi()["components"]["schemas"]["Certificate"]["properties"]
    assert certificate["verdict"]["enum"] == contract


IMPLEMENTED = {
    ("/health", "get"),
    ("/capabilities", "get"),
    ("/templates", "get"),
    ("/runs", "get"),
    ("/runs", "post"),
    ("/runs/{run_id}", "get"),
    ("/runs/{run_id}/events", "get"),
    ("/runs/{run_id}/cancel", "post"),
}


def _schema(name: str) -> dict:
    return load_openapi()["components"]["schemas"][name]


def test_implemented_routes_use_contract_operation_ids(client: TestClient) -> None:
    served = client.get("/openapi.json").json()["paths"]
    contract = load_openapi()["paths"]
    for path, method in IMPLEMENTED:
        assert (
            served[API_PREFIX + path][method]["operationId"]
            == (contract[path][method]["operationId"])
        ), (path, method)


def test_no_route_is_served_outside_the_contract(client: TestClient) -> None:
    served = client.get("/openapi.json").json()["paths"]
    contract = load_openapi()["paths"]
    for path, methods in served.items():
        assert path.startswith(API_PREFIX), path
        for method in methods:
            assert method in contract[path.removeprefix(API_PREFIX)], (path, method)


def test_capabilities_response_matches_contract(client: TestClient) -> None:
    body = client.get("/api/v1/capabilities").json()
    schema = _schema("Capabilities")
    assert set(body) == set(schema["properties"]) == set(schema["required"])


def test_template_response_matches_contract(api: TestClient) -> None:
    schema = _schema("Template")
    for template in api.get("/api/v1/templates").json():
        assert set(template) == set(schema["properties"])
        assert template["expected_verdict"] in schema["properties"]["expected_verdict"]["enum"]


def test_run_and_event_responses_match_contract(api: TestClient) -> None:
    run = api.post("/api/v1/runs", json={"template_id": "success-validation"}).json()
    run_schema = _schema("Run")
    assert set(run_schema["required"]) <= set(run) <= set(run_schema["properties"])

    event_schema = _schema("Event")
    for event in api.get(f"/api/v1/runs/{run['id']}/events").json():
        assert set(event) == set(event_schema["properties"]) == set(event_schema["required"])
        assert event["event_type"] in event_schema["properties"]["event_type"]["enum"]
        assert event["actor"] in event_schema["properties"]["actor"]["enum"]


def test_event_and_actor_enums_match_contract() -> None:
    props = _schema("Event")["properties"]
    assert [e.value for e in EventType] == props["event_type"]["enum"]
    assert [a.value for a in Actor] == props["actor"]["enum"]


def test_error_codes_match_contract() -> None:
    codes = _schema("ErrorResponse")["properties"]["error"]["properties"]["code"]["enum"]
    assert [c.value for c in ErrorCode] == codes


def test_challenge_schema_loads() -> None:
    assert load_schemas()["additionalProperties"] is False
