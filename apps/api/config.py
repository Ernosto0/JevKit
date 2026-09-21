"""API service settings.

Provider credentials stay server-side and are never returned to clients
(PLAN.md section 14).
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Configuration for the FastAPI service only. SDK settings live separately."""

    model_config = SettingsConfigDict(
        env_prefix="JEVKIT_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    title: str = "JevKit API"
    environment: str = "development"
    debug: bool = False

    # Comma-separated list of accepted client API keys. Empty disables auth,
    # which is acceptable for local development only.
    api_keys: str = ""

    database_url: str = Field(
        default="postgresql+asyncpg://jevkit:jevkit@localhost:5432/jevkit",
        alias="JEVKIT_DATABASE_URL",
    )

    cors_origins: str = "http://localhost:5173"
    max_request_bytes: int = 256_000
    max_concurrent_decisions: int = 16
    request_timeout_seconds: float = 30.0

    admin_token: SecretStr | None = None

    @property
    def allowed_api_keys(self) -> set[str]:
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}

    @property
    def auth_required(self) -> bool:
        return bool(self.allowed_api_keys)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


_settings: ApiSettings | None = None


def get_api_settings() -> ApiSettings:
    global _settings
    if _settings is None:
        _settings = ApiSettings()
    return _settings
