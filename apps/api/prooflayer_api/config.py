"""Environment-driven settings.

Secrets are held as ``SecretStr`` so they never appear in ``repr``, logs or
API responses. The service boots with no cloud credentials in mock mode.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_NEBIUS_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/"


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

    # Hard limits (enforced by later milestones; declared here so they are configured once).
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
