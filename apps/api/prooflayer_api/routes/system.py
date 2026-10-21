"""Health and capability routes."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from ..config import Settings, get_settings
from ..services.runtime import SandboxStatusCache, build_sandbox_driver

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
    # The independent verifier lands in Commit 09; until then this stays False.
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


def build_capabilities(
    settings: Settings, sandbox: SandboxStatusCache | None = None
) -> CapabilitiesResponse:
    enforced = sandbox.enforced if sandbox is not None else False
    return CapabilitiesResponse(
        mock_mode=settings.mock_mode,
        nebius_configured=settings.nebius_configured,
        live_model_enabled=settings.nebius_configured and not settings.mock_mode,
        openshell_available=enforced,
        sandbox_enforced=enforced,
        independent_verifier_available=False,
        tavily_enabled=settings.tavily_configured,
    )


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health() -> HealthResponse:
    return HealthResponse()


@router.get("/capabilities", response_model=CapabilitiesResponse, operation_id="getCapabilities")
def get_capabilities(settings: SettingsDep, sandbox: SandboxStatusDep) -> CapabilitiesResponse:
    return build_capabilities(settings, sandbox)
