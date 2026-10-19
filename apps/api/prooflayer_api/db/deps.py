"""Request-scoped database sessions."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError("database not initialised; the app lifespan has not run")
    session = session_factory()
    try:
        yield session
    finally:
        # Releases the SQLite write lock if a handler returned without committing.
        session.close()
