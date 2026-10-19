"""Engine and session factory."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

SQLITE_BUSY_TIMEOUT_SECONDS = 10


def make_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    is_sqlite = url.get_backend_name() == "sqlite"
    connect_args: dict = {}
    if is_sqlite:
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = SQLITE_BUSY_TIMEOUT_SECONDS
        if url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args=connect_args)

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _record) -> None:
            # Let SQLAlchemy own transaction boundaries (see _begin_immediate).
            dbapi_connection.isolation_level = None
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        @event.listens_for(engine, "begin")
        def _begin_immediate(connection) -> None:
            # Take the write lock up front so concurrent writers queue on the
            # busy timeout instead of failing on a deferred lock upgrade. This
            # serialises event sequence allocation per database.
            connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
