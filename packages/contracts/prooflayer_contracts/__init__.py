"""Loaders for the canonical API contracts in the repository's ``contracts/`` directory.

The YAML/JSON files stay the single source of truth; this package only reads
them so backend code and tests can assert they agree with the contract.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
OPENAPI_PATH = CONTRACTS_DIR / "openapi.yaml"
SCHEMAS_PATH = CONTRACTS_DIR / "schemas.json"


@lru_cache
def load_openapi() -> dict[str, Any]:
    return yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))


@lru_cache
def load_schemas() -> dict[str, Any]:
    return json.loads(SCHEMAS_PATH.read_text(encoding="utf-8"))


def api_prefix() -> str:
    """Path prefix of the first declared server, e.g. ``/api/v1``."""
    url = load_openapi()["servers"][0]["url"]
    return "/" + url.split("://", 1)[-1].split("/", 1)[1].strip("/")


def component_enum(schema: str, prop: str) -> list[Any]:
    """Enum values of ``components.schemas.<schema>.properties.<prop>``."""
    return list(load_openapi()["components"]["schemas"][schema]["properties"][prop]["enum"])
