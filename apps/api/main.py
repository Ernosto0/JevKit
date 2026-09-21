"""FastAPI application entry point.

Run locally::

    uvicorn apps.api.main:app --reload

The service is a thin layer over `packages/jevkit`: it owns transport, auth and
persistence, never decision logic (PLAN.md section 7).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.config import get_api_settings
from apps.api.routes import benchmarks, decisions, health, tasks
from jevkit.__about__ import __version__
from jevkit.errors import (
    ConfigurationError,
    InputValidationError,
    JevKitError,
    PolicyError,
    ProviderError,
    TaskDefinitionError,
)
from jevkit.providers.jev.schema import SCHEMA_VERIFIED

logger = logging.getLogger("jevkit.api")

API_PREFIX = "/v1"

DESCRIPTION = """
JevKit's HTTP API: define typed decision tasks, execute them, inspect traces,
and benchmark providers against labeled datasets.

Decisions returned here are recommendations. Authorization and any resulting
action remain the calling application's responsibility.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_api_settings()
    if not settings.auth_required:
        logger.warning(
            "No JEVKIT_API_API_KEYS configured: the API is unauthenticated. "
            "This is acceptable for local development only."
        )
    if not SCHEMA_VERIFIED:
        logger.warning(
            "The Jev request/response mapping is still provisional. "
            "Verify it against the official API before relying on results."
        )
    yield


def create_app() -> FastAPI:
    """Build the ASGI application."""
    settings = get_api_settings()
    app = FastAPI(
        title=settings.title,
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def limit_request_size(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Reject oversized bodies before they reach a route (PLAN.md section 14)."""
        declared = request.headers.get("content-length")
        if declared and int(declared) > settings.max_request_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"Request body exceeds {settings.max_request_bytes} bytes."},
            )
        return await call_next(request)

    @app.exception_handler(JevKitError)
    async def handle_jevkit_error(_request: Request, exc: JevKitError) -> JSONResponse:
        """Map library errors onto safe HTTP responses; never leak internals."""
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if isinstance(exc, (InputValidationError, TaskDefinitionError)):
            code = status.HTTP_422_UNPROCESSABLE_ENTITY
        elif isinstance(exc, ProviderError):
            code = status.HTTP_502_BAD_GATEWAY
        elif isinstance(exc, ConfigurationError):
            code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif isinstance(exc, PolicyError):
            code = status.HTTP_409_CONFLICT

        logger.warning("%s: %s", type(exc).__name__, exc.message)
        return JSONResponse(
            status_code=code,
            content={
                "detail": exc.message,
                "error": type(exc).__name__,
                "trace_id": exc.trace_id,
            },
        )

    app.include_router(health.router)
    app.include_router(decisions.router, prefix=API_PREFIX)
    app.include_router(tasks.router, prefix=API_PREFIX)
    app.include_router(benchmarks.router, prefix=API_PREFIX)
    return app


app = create_app()
