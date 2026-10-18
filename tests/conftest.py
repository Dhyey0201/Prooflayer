from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from prooflayer_api.config import Settings
from prooflayer_api.main import create_app

_SETTINGS_ENV = (
    "PROOFLAYER_ENV",
    "PROOFLAYER_MOCK_MODE",
    "DATABASE_URL",
    "PROOFLAYER_CORS_ORIGINS",
    "NEBIUS_API_KEY",
    "NEBIUS_BASE_URL",
    "NEBIUS_MODEL_ID",
    "TAVILY_API_KEY",
)

# Obviously fake; used to prove key values never leave the server.
FAKE_NEBIUS_KEY = "nb-test-DO-NOT-LEAK-0123456789abcdef"


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ignore the developer's shell environment so tests are deterministic."""
    for name in _SETTINGS_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    def _make(**values: object) -> Settings:
        # _env_file=None: never read a local .env during tests.
        return Settings(_env_file=None, **values)

    return _make


@pytest.fixture
def client(make_settings: Callable[..., Settings]) -> TestClient:
    return TestClient(create_app(make_settings()))
