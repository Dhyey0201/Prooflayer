from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from prooflayer_api.db.models import Base
from prooflayer_api.db.session import make_engine

API_DIR = Path(__file__).resolve().parents[1] / "apps" / "api"
TABLES = {"task_templates", "runs", "events", "artifacts", "checks", "certificates"}


def _alembic_config(url: str) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'nested' / 'test.db'}"


def test_upgrade_creates_all_tables_and_downgrade_removes_them(db_url: str) -> None:
    config = _alembic_config(db_url)
    command.upgrade(config, "head")
    engine = make_engine(db_url)
    assert set(inspect(engine).get_table_names()) >= TABLES

    command.downgrade(config, "base")
    assert not TABLES & set(inspect(engine).get_table_names())
    engine.dispose()


def test_models_match_migrations(db_url: str) -> None:
    command.upgrade(_alembic_config(db_url), "head")
    engine = make_engine(db_url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []


def test_status_check_constraint_rejects_unknown_values(db_url: str) -> None:
    command.upgrade(_alembic_config(db_url), "head")
    engine = make_engine(db_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO task_templates VALUES "
                "('success-validation', 't', 'sha', '[]', '[]', 'v1')"
            )
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO runs (id, task_id, status, mode, created_at, updated_at) VALUES "
                "('r1', 'success-validation', 'secure', 'fixture', "
                "'2026-10-19', '2026-10-19')"
            )
        )
    engine.dispose()


def test_event_sequence_is_unique_per_run(db_url: str) -> None:
    command.upgrade(_alembic_config(db_url), "head")
    engine = make_engine(db_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO task_templates VALUES "
                "('success-validation', 't', 'sha', '[]', '[]', 'v1')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO runs (id, task_id, status, mode, created_at, updated_at) VALUES "
                "('r1', 'success-validation', 'created', 'fixture', "
                "'2026-10-19', '2026-10-19')"
            )
        )
    insert_event = text(
        "INSERT INTO events (run_id, seq, time, type, actor, payload_json, prev_hash, "
        "event_hash) VALUES ('r1', 1, '2026-10-19', 'run.created', 'api', '{}', '0', 'h')"
    )
    with engine.begin() as connection:
        connection.execute(insert_event)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert_event)
    engine.dispose()
