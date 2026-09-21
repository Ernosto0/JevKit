"""The Jev provider adapter.

Transport concerns (auth, timeouts, status-code -> typed-error mapping) are
handled here. The request/response *shape* lives in `schema.py` and is still
provisional -- see the banner in that module.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from jevkit.config import JevKitSettings, get_settings
from jevkit.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from jevkit.providers.base import ModelProvider, ProviderRequest, ProviderResponse
from jevkit.providers.jev.schema import build_request_payload, parse_response_payload

__all__ = ["JevProvider"]


class JevProvider(ModelProvider):
    """Calls the Jev API for structured decisions.

    JevKit is an independent project. Jev is developed by TypeSafe AI, and this
    adapter is not an official client.
    """

    name = "jev"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        settings: JevKitSettings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._api_key = api_key or cfg.require_jev_api_key()
        self._base_url = (base_url or cfg.jev_base_url).rstrip("/")
        self._model = model or cfg.jev_model
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._auth_headers(),
            timeout=cfg.timeout_seconds,
        )

    def _auth_headers(self) -> dict[str, str]:
        # Auth scheme is provisional; confirm against the official docs (Phase 1).
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "jevkit-python",
        }

    async def decide(self, request: ProviderRequest) -> ProviderResponse:
        payload = build_request_payload(request.task, request.state)
        if self._model:
            payload["model"] = self._model

        started = time.perf_counter()
        try:
            http_response = await self._client.post(
                "/decisions",
                json=payload,
                timeout=request.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"Jev did not respond within {request.timeout_seconds}s",
                provider=self.name,
                trace_id=request.trace_id,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderResponseError(
                f"Transport error calling Jev: {exc}",
                provider=self.name,
                trace_id=request.trace_id,
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        self._raise_for_status(http_response, trace_id=request.trace_id)

        try:
            body: Any = http_response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                "Jev returned a non-JSON body",
                provider=self.name,
                status_code=http_response.status_code,
                trace_id=request.trace_id,
            ) from exc

        if not isinstance(body, dict):
            raise ProviderResponseError(
                f"Jev returned a JSON {type(body).__name__}, expected an object",
                provider=self.name,
                trace_id=request.trace_id,
            )

        decisions, confidence = parse_response_payload(body)
        return ProviderResponse(
            decisions=decisions,
            confidence=confidence,
            model=body.get("model") or self._model,
            latency_ms=latency_ms,
            raw=body,
        )

    def _raise_for_status(self, response: httpx.Response, *, trace_id: str | None) -> None:
        """Map HTTP status codes onto JevKit's typed provider errors."""
        status = response.status_code
        if status < 400:
            return

        detail = _safe_detail(response)
        if status in (401, 403):
            raise ProviderAuthError(
                f"Jev rejected the credentials ({status}): {detail}",
                provider=self.name,
                status_code=status,
                trace_id=trace_id,
            )
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            raise ProviderRateLimitError(
                f"Jev rate limit reached: {detail}",
                retry_after=float(retry_after) if retry_after else None,
                provider=self.name,
                status_code=status,
                trace_id=trace_id,
            )
        if status >= 500:
            error = ProviderResponseError(
                f"Jev server error ({status}): {detail}",
                provider=self.name,
                status_code=status,
                trace_id=trace_id,
            )
            error.retryable = True  # transient by nature
            raise error
        raise ProviderResponseError(
            f"Jev rejected the request ({status}): {detail}",
            provider=self.name,
            status_code=status,
            trace_id=trace_id,
        )

    async def aclose(self) -> None:
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()


def _safe_detail(response: httpx.Response, limit: int = 300) -> str:
    """Short, credential-free description of an error body."""
    try:
        text = response.text
    except Exception:  # pragma: no cover - defensive
        return "<unreadable body>"
    return text[:limit].replace("\n", " ").strip() or "<empty body>"
