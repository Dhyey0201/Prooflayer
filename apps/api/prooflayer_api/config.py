"""Environment-driven settings.

Secrets are held as ``SecretStr`` so they never appear in ``repr``, logs or
API responses. The service boots with no cloud credentials in mock mode.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_NEBIUS_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/"


class SandboxDriverName(StrEnum):
    # Deterministic in-process double; reports enforced=False on every event.
    MOCK = "mock"
    # NVIDIA OpenShell CLI + gateway; enforcement is confirmed per sandbox.
    OPENSHELL = "openshell"


class VerifierDriverName(StrEnum):
    # Fresh network-less container per check on the local Docker engine.
    DOCKER = "docker"
    # No verifier runtime: every executed check is INCONCLUSIVE.
    DISABLED = "disabled"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="development", alias="PROOFLAYER_ENV")
    # Mock mode uses deterministic test doubles instead of Nebius/OpenShell.
    mock_mode: bool = Field(default=True, alias="PROOFLAYER_MOCK_MODE")
    database_url: str = Field(default="sqlite:///./data/prooflayer.db", alias="DATABASE_URL")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"], alias="PROOFLAYER_CORS_ORIGINS"
    )

    nebius_api_key: SecretStr | None = Field(default=None, alias="NEBIUS_API_KEY")
    nebius_base_url: str = Field(default=DEFAULT_NEBIUS_BASE_URL, alias="NEBIUS_BASE_URL")
    # Model IDs are configuration, never hard-coded guesses; confirm via GET /v1/models.
    nebius_model_id: str = Field(
        default="nvidia/nemotron-3-super-120b-a12b", alias="NEBIUS_MODEL_ID"
    )
    tavily_api_key: SecretStr | None = Field(default=None, alias="TAVILY_API_KEY")
    model_timeout_seconds: float = Field(
        default=30.0, gt=0, le=300, alias="PROOFLAYER_MODEL_TIMEOUT_SECONDS"
    )
    # Extra attempts after a retryable model error (timeout, 429, 5xx).
    model_max_retries: int = Field(default=2, ge=0, le=5, alias="PROOFLAYER_MODEL_MAX_RETRIES")

    sandbox_driver: SandboxDriverName = Field(
        default=SandboxDriverName.MOCK, alias="SANDBOX_DRIVER"
    )
    openshell_bin: str = Field(default="openshell", alias="OPENSHELL_BIN")
    # Local image holding the fixture workspaces (`make sandbox-image`).
    sandbox_image: str = Field(
        default="prooflayer-workspace:0.1.0", alias="PROOFLAYER_SANDBOX_IMAGE"
    )
    sandbox_cpu: str = Field(default="1", pattern=r"^[0-9]+(\.[0-9]+)?m?$", alias="SANDBOX_CPU")
    sandbox_memory: str = Field(default="1Gi", pattern=r"^[0-9]+(Mi|Gi)$", alias="SANDBOX_MEMORY")

    # Independent verifier (separate image, identity and container per check).
    verifier_driver: VerifierDriverName = Field(
        default=VerifierDriverName.DOCKER, alias="VERIFIER_DRIVER"
    )
    docker_bin: str = Field(default="docker", alias="DOCKER_BIN")
    verifier_image: str = Field(default="prooflayer-verifier:0.1.0", alias="VERIFIER_IMAGE")
    # Optional pin: refuse to verify unless the image ID matches exactly.
    verifier_image_id: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$", alias="VERIFIER_IMAGE_ID"
    )
    verifier_cpus: str = Field(default="1", pattern=r"^[0-9]+(\.[0-9]+)?$", alias="VERIFIER_CPUS")
    verifier_memory: str = Field(default="512m", pattern=r"^[0-9]+[mg]$", alias="VERIFIER_MEMORY")
    verifier_pids_limit: int = Field(default=128, ge=16, le=1024, alias="VERIFIER_PIDS_LIMIT")
    verifier_timeout_seconds: int = Field(
        default=60, ge=5, le=600, alias="VERIFIER_TIMEOUT_SECONDS"
    )
    # Detached append-only ledger of certificate digests; empty disables it.
    evidence_ledger_path: str = Field(
        default="./data/evidence-ledger.jsonl", alias="PROOFLAYER_EVIDENCE_LEDGER"
    )
    max_challenges_per_run: int = Field(
        default=3, ge=0, le=20, alias="PROOFLAYER_MAX_CHALLENGES_PER_RUN"
    )

    # Background worker that advances queued runs; tests turn it off.
    worker_enabled: bool = Field(default=True, alias="PROOFLAYER_WORKER_ENABLED")
    worker_poll_seconds: float = Field(
        default=1.0, gt=0, le=60, alias="PROOFLAYER_WORKER_POLL_SECONDS"
    )

    # Hard limits, configured once. Concurrency, run duration, output bytes, model
    # tokens/calls and agent steps are enforced by the worker and agent loop.
    max_concurrent_runs: int = Field(default=1, ge=1, le=4, alias="PROOFLAYER_MAX_CONCURRENT_RUNS")
    # Non-terminal runs allowed at once; POST /runs returns 429 beyond this.
    max_pending_runs: int = Field(default=10, ge=1, le=100, alias="PROOFLAYER_MAX_PENDING_RUNS")
    max_run_seconds: int = Field(default=120, ge=1, le=900, alias="PROOFLAYER_MAX_RUN_SECONDS")
    max_output_bytes: int = Field(
        default=1_000_000, ge=1_024, le=10_000_000, alias="PROOFLAYER_MAX_OUTPUT_BYTES"
    )
    max_model_tokens: int = Field(
        default=20_000, ge=1, le=200_000, alias="PROOFLAYER_MAX_MODEL_TOKENS"
    )
    max_model_calls_per_run: int = Field(
        default=12, ge=1, le=100, alias="PROOFLAYER_MAX_MODEL_CALLS_PER_RUN"
    )
    max_agent_steps: int = Field(default=8, ge=1, le=50, alias="PROOFLAYER_MAX_AGENT_STEPS")

    @field_validator("verifier_image_id", mode="before")
    @classmethod
    def _blank_pin_means_unpinned(cls, value: object) -> object:
        # `.env.example` ships `VERIFIER_IMAGE_ID=`; an empty value is no pin, not a bad one.
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _require_key_outside_mock_mode(self) -> Settings:
        if not self.mock_mode and not self.nebius_configured:
            raise ValueError("NEBIUS_API_KEY is required when PROOFLAYER_MOCK_MODE=false")
        return self

    @property
    def nebius_configured(self) -> bool:
        return self.nebius_api_key is not None and bool(self.nebius_api_key.get_secret_value())

    @property
    def tavily_configured(self) -> bool:
        return self.tavily_api_key is not None and bool(self.tavily_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
