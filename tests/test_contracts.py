"""The API must agree with contracts/openapi.yaml, which is canonical."""

from __future__ import annotations

from fastapi.testclient import TestClient

from prooflayer_api.enums import RunMode, RunStatus, TemplateId, Verdict
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


def test_implemented_routes_use_contract_operation_ids(client: TestClient) -> None:
    served = client.get("/openapi.json").json()["paths"]
    contract = load_openapi()["paths"]
    for path in ("/health", "/capabilities"):
        assert (
            served[API_PREFIX + path]["get"]["operationId"]
            == (contract[path]["get"]["operationId"])
        )


def test_challenge_schema_loads() -> None:
    assert load_schemas()["additionalProperties"] is False
