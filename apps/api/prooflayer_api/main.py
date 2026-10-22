"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from . import __version__
from .config import Settings, get_settings
from .db.session import make_engine, make_session_factory
from .errors import UnhandledErrorMiddleware, register_error_handlers
from .request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from .routes import runs, system
from .services.fixtures import seed_templates
from .services.runtime import Runtime, SandboxStatusCache, build_runtime
from .services.worker import RunWorker

API_PREFIX = "/api/v1"


class DatabaseNotMigratedError(RuntimeError):
    pass


def _lifespan(settings: Settings, runtime: Runtime | None):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        if not inspect(engine).has_table("task_templates"):
            engine.dispose()
            raise DatabaseNotMigratedError(
                "Database schema missing; run `make migrate` (alembic upgrade head) first"
            )
        session_factory = make_session_factory(engine)
        # The registry in code is authoritative; mirror it into the DB on boot.
        with session_factory.begin() as session:
            seed_templates(session)
        app.state.session_factory = session_factory
        run_runtime = runtime or build_runtime(settings)
        app.state.runtime = run_runtime
        app.state.sandbox_status = SandboxStatusCache(run_runtime.driver)
        worker = RunWorker(session_factory, run_runtime) if settings.worker_enabled else None
        app.state.worker = worker
        if worker is not None:
            worker.start()
        try:
            yield
        finally:
            if worker is not None:
                worker.stop()
            engine.dispose()

    return lifespan


def create_app(settings: Settings | None = None, runtime: Runtime | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()
        overrides = {}
    else:
        overrides = {get_settings: lambda: settings}
    app = FastAPI(
        title="ProofLayer API", version=__version__, lifespan=_lifespan(settings, runtime)
    )
    app.dependency_overrides.update(overrides)

    register_error_handlers(app)
    # Middleware added later wraps earlier ones: RequestId is outermost so the
    # typed 500 from UnhandledErrorMiddleware still carries the request ID.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, "Idempotent-Replayed"],
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(system.router, prefix=API_PREFIX)
    app.include_router(runs.router, prefix=API_PREFIX)
    # Unprefixed liveness probe for containers and load balancers.
    app.add_api_route("/health", system.get_health, methods=["GET"], include_in_schema=False)
    return app


app = create_app()
