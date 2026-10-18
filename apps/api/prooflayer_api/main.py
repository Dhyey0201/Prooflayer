"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import Settings, get_settings
from .errors import UnhandledErrorMiddleware, register_error_handlers
from .request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from .routes import system

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="ProofLayer API", version=__version__)
    if settings is None:
        settings = get_settings()
    else:
        app.dependency_overrides[get_settings] = lambda: settings

    register_error_handlers(app)
    # Middleware added later wraps earlier ones: RequestId is outermost so the
    # typed 500 from UnhandledErrorMiddleware still carries the request ID.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(system.router, prefix=API_PREFIX)
    # Unprefixed liveness probe for containers and load balancers.
    app.add_api_route("/health", system.get_health, methods=["GET"], include_in_schema=False)
    return app


app = create_app()
