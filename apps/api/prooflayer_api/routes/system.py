"""Health and capability routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from ..config import Settings, get_settings
from ..enums import ErrorCode
from ..errors import ApiError
from ..services.runtime import (
    SandboxStatusCache,
    VerifierStatusCache,
    build_sandbox_driver,
    build_verifier_driver,
)

router = APIRouter(tags=["system"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class CapabilitiesResponse(BaseModel):
    """Boolean availability flags only. Never carries secrets, URLs or model IDs."""

    model_config = ConfigDict(extra="forbid")

    mock_mode: bool
    nebius_configured: bool
    live_model_enabled: bool
    # True only when SANDBOX_DRIVER=openshell and the CLI + gateway answer.
    # Each sandbox's enforcement is confirmed again when it is provisioned.
    openshell_available: bool
    sandbox_enforced: bool
    # Live runs may use the unenforced mock sandbox (development fallback, opt-in).
    unenforced_live_allowed: bool
    # The verifier runtime answers and its pinned image is present.
    independent_verifier_available: bool
    tavily_enabled: bool


def get_sandbox_status(request: Request, settings: SettingsDep) -> SandboxStatusCache:
    """Probe cache created by the app lifespan (or lazily without one)."""
    status = getattr(request.app.state, "sandbox_status", None)
    if status is None:
        status = SandboxStatusCache(build_sandbox_driver(settings))
        request.app.state.sandbox_status = status
    return status


SandboxStatusDep = Annotated[SandboxStatusCache, Depends(get_sandbox_status)]


def get_verifier_status(request: Request, settings: SettingsDep) -> VerifierStatusCache:
    status = getattr(request.app.state, "verifier_status", None)
    if status is None:
        status = VerifierStatusCache(build_verifier_driver(settings))
        request.app.state.verifier_status = status
    return status


VerifierStatusDep = Annotated[VerifierStatusCache, Depends(get_verifier_status)]


def build_capabilities(
    settings: Settings,
    sandbox: SandboxStatusCache | None = None,
    verifier: VerifierStatusCache | None = None,
) -> CapabilitiesResponse:
    enforced = sandbox.enforced if sandbox is not None else False
    return CapabilitiesResponse(
        mock_mode=settings.mock_mode,
        nebius_configured=settings.nebius_configured,
        live_model_enabled=settings.nebius_configured and not settings.mock_mode,
        openshell_available=enforced,
        sandbox_enforced=enforced,
        unenforced_live_allowed=settings.allow_unenforced_live,
        independent_verifier_available=verifier.get().available if verifier else False,
        tavily_enabled=settings.tavily_configured,
    )


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health() -> HealthResponse:
    return HealthResponse()


@router.get("/capabilities", response_model=CapabilitiesResponse, operation_id="getCapabilities")
def get_capabilities(
    settings: SettingsDep, sandbox: SandboxStatusDep, verifier: VerifierStatusDep
) -> CapabilitiesResponse:
    return build_capabilities(settings, sandbox, verifier)


@router.get("/benchmark", operation_id="getBenchmarkReport")
def get_benchmark_report(settings: SettingsDep) -> JSONResponse:
    """The published benchmark report, exactly as `make benchmark` wrote it."""
    path = Path(settings.benchmark_report_path)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ApiError(404, ErrorCode.NOT_FOUND, "No benchmark report has been published") from None
    if not isinstance(report, dict):
        raise ApiError(404, ErrorCode.NOT_FOUND, "No benchmark report has been published")
    return JSONResponse(report)
