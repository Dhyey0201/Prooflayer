from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from prooflayer_api.config import Settings
from prooflayer_api.db.session import make_engine, make_session_factory
from prooflayer_api.main import create_app
from prooflayer_api.services.fixtures import seed_templates

_SETTINGS_ENV = (
    "PROOFLAYER_ENV",
    "PROOFLAYER_MOCK_MODE",
    "DATABASE_URL",
    "PROOFLAYER_CORS_ORIGINS",
    "NEBIUS_API_KEY",
    "NEBIUS_BASE_URL",
    "NEBIUS_MODEL_ID",
    "TAVILY_API_KEY",
    "PROOFLAYER_MAX_PENDING_RUNS",
    "PROOFLAYER_WORKER_ENABLED",
    "SANDBOX_DRIVER",
    "OPENSHELL_BIN",
    "PROOFLAYER_SANDBOX_IMAGE",
    "RUN_LIVE_INTEGRATION",
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
        # _env_file=None: never read a local .env during tests. The background
        # worker is off unless a test turns it on, so runs stay where tests put them.
        values.setdefault("PROOFLAYER_WORKER_ENABLED", False)
        return Settings(_env_file=None, **values)

    return _make


@pytest.fixture
def client(make_settings: Callable[..., Settings]) -> TestClient:
    return TestClient(create_app(make_settings()))


API_DIR = Path(__file__).resolve().parents[1] / "apps" / "api"


def alembic_config(url: str) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'nested' / 'test.db'}"


@pytest.fixture
def migrated_db_url(db_url: str) -> str:
    command.upgrade(alembic_config(db_url), "head")
    return db_url


@pytest.fixture
def session_factory(migrated_db_url: str) -> Iterator[sessionmaker]:
    engine = make_engine(migrated_db_url)
    factory = make_session_factory(engine)
    with factory.begin() as session:
        seed_templates(session)
    yield factory
    engine.dispose()


@pytest.fixture
def api(make_settings: Callable[..., Settings], migrated_db_url: str) -> Iterator[TestClient]:
    """Client with the app lifespan running against a migrated temp database."""
    app = create_app(make_settings(DATABASE_URL=migrated_db_url))
    with TestClient(app) as client:
        yield client
