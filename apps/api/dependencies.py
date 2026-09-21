"""Shared FastAPI dependencies: auth, concurrency limiting, client construction."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from apps.api.config import ApiSettings, get_api_settings
from jevkit.client.client import DecisionClient
from jevkit.config import get_settings
from jevkit.errors import ConfigurationError

__all__ = ["ApiKey", "Client", "Settings", "require_api_key"]

Settings = Annotated[ApiSettings, Depends(get_api_settings)]

# Bounded concurrency for outbound provider calls (PLAN.md section 14). Created
# lazily so the limit follows configuration rather than import order.
_semaphore: asyncio.Semaphore | None = None


def _decision_semaphore(settings: ApiSettings) -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_decisions)
    return _semaphore


async def require_api_key(
    settings: Settings,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str | None:
    """Reject requests without a known client API key.

    Auth is skipped entirely when no keys are configured, which is intended for
    local development only -- never for a hosted deployment.
    """
    if not settings.auth_required:
        return None
    if x_api_key is None or x_api_key not in settings.allowed_api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-API-Key header is required.",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
    return x_api_key


ApiKey = Annotated[str | None, Depends(require_api_key)]


async def get_client(settings: Settings) -> AsyncIterator[DecisionClient]:
    """Provide a DecisionClient, bounded by the service's concurrency limit.

    Provider credentials come from server-side environment configuration and
    are never accepted from, or returned to, a client.
    """
    async with _decision_semaphore(settings):
        try:
            client = DecisionClient.from_env(settings=get_settings())
        except ConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Provider not configured: {exc.message}",
            ) from exc
        try:
            yield client
        finally:
            await client.aclose()


Client = Annotated[DecisionClient, Depends(get_client)]
