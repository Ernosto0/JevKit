"""Environment-based configuration.

Secrets are read from the environment (or a local .env) and never written to a
trace or log. See PLAN.md §17.
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class JevKitSettings(BaseSettings):
    """Configuration for the SDK and, by extension, the API service."""

    model_config = SettingsConfigDict(
        env_prefix="JEVKIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Primary provider: Jev ---
    # Verified against the live API on 2026-09-21; see docs/jev-api-notes.md.
    # Note that keys from jevai.org are NOT valid here -- that is a separate
    # service with its own endpoint. Get a key at console.typesafe.ai.
    jev_api_key: SecretStr | None = Field(default=None, alias="JEV_API_KEY")
    jev_base_url: str = Field(default="https://api.typesafe.ai/v1", alias="JEV_BASE_URL")
    jev_model: str = Field(default="jev-latest", alias="JEV_MODEL")

    # --- Optional reference / fallback provider ---
    fallback_provider: str | None = None
    fallback_api_key: SecretStr | None = None
    fallback_base_url: str | None = None
    fallback_model: str | None = None

    # --- Execution defaults (a DecisionPolicy may override these per call) ---
    timeout_seconds: float = 10.0
    max_retries: int = 1
    max_concurrency: int = 8

    # --- Tracing ---
    trace_enabled: bool = True
    trace_store_inputs: bool = False  # off by default: inputs may be sensitive
    trace_dir: str = ".jevkit/traces"

    def require_jev_api_key(self) -> str:
        """Return the Jev API key or raise a clear configuration error."""
        from jevkit.errors import ConfigurationError

        if self.jev_api_key is None:
            raise ConfigurationError(
                "No Jev API key configured. Set JEV_API_KEY in the environment "
                "or pass api_key= explicitly when constructing the provider."
            )
        return self.jev_api_key.get_secret_value()

    def require_fallback_api_key(self) -> str:
        """Return the reference/fallback provider's API key or raise a clear error."""
        from jevkit.errors import ConfigurationError

        if self.fallback_api_key is None:
            raise ConfigurationError(
                "No reference/fallback provider API key configured. Set "
                "JEVKIT_FALLBACK_API_KEY in the environment or pass api_key= "
                "explicitly when constructing the provider."
            )
        return self.fallback_api_key.get_secret_value()


_settings: JevKitSettings | None = None


def get_settings(*, refresh: bool = False) -> JevKitSettings:
    """Return the process-wide settings, loading them on first use."""
    global _settings
    if _settings is None or refresh:
        _settings = JevKitSettings()
    return _settings
