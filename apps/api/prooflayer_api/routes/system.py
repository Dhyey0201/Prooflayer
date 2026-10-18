"""Health and capability routes."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from ..config import Settings, get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class CapabilitiesResponse(BaseModel):
    """Boolean availability flags only. Never carries secrets, URLs or model IDs."""

    model_config = ConfigDict(extra="forbid")

    mock_mode: bool
    nebius_configured: bool
    live_model_enabled: bool
    # Sandbox and verifier drivers land in later milestones. Until a real
    # OpenShell session is detected these stay False; nothing is claimed as enforced.
    openshell_available: bool
    sandbox_enforced: bool
    independent_verifier_available: bool
    tavily_enabled: bool


def build_capabilities(settings: Settings) -> CapabilitiesResponse:
    return CapabilitiesResponse(
        mock_mode=settings.mock_mode,
        nebius_configured=settings.nebius_configured,
        live_model_enabled=settings.nebius_configured and not settings.mock_mode,
        openshell_available=False,
        sandbox_enforced=False,
        independent_verifier_available=False,
        tavily_enabled=settings.tavily_configured,
    )


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health() -> HealthResponse:
    return HealthResponse()


@router.get("/capabilities", response_model=CapabilitiesResponse, operation_id="getCapabilities")
def get_capabilities(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CapabilitiesResponse:
    return build_capabilities(settings)
