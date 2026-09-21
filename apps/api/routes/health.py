"""Health endpoint. Unauthenticated by design, and free of any secret."""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.dependencies import Settings
from apps.api.schemas.decisions import HealthResponse
from jevkit.__about__ import __version__
from jevkit.providers.jev.schema import SCHEMA_VERIFIED

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health(settings: Settings) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.environment,
        jev_schema_verified=SCHEMA_VERIFIED,
    )
