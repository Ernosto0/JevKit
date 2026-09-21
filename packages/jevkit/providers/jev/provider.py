"""The Jev provider adapter.

Transport concerns (auth, timeouts, status-code -> typed-error mapping) are
handled here; the request/response shape lives in `schema.py`. Both were
verified against the live API in phase 1 -- see docs/jev-api-notes.md.
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
from jevkit.providers.jev.schema import (
    build_request_payload,
    parse_response_payload,
    parse_usage,
)

__all__ = ["DEFAULT_MODEL", "ENDPOINT", "JevProvider"]

ENDPOINT = "/systemone"
"""Path appended to the base URL. Verified: `/decisions` is a 404."""

DEFAULT_MODEL = "jev-latest"
"""Sent when no model is configured. The API requires one -- omitting it is a 422."""


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
        self._model = model or cfg.jev_model or DEFAULT_MODEL
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._auth_headers(),
            timeout=cfg.timeout_seconds,
        )

    def _auth_headers(self) -> dict[str, str]:
        # Verified: no header -> 403, bad key -> 401.
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "jevkit-python",
        }

    async def decide(self, request: ProviderRequest) -> ProviderResponse:
        payload = build_request_payload(request.task, request.state, model=self._model)

        started = time.perf_counter()
        try:
            http_response = await self._client.post(
                ENDPOINT,
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
            usage=parse_usage(body),
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
            raise ProviderRateLimitError(
                f"Jev rate limit reached: {detail}",
                retry_after=_retry_after_seconds(response),
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


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Seconds to wait before retrying, from whichever channel carries it.

    The documented SDK exposes `retry_after_ms`; a `Retry-After` header in
    seconds is the HTTP convention. Neither has been observed live, so both are
    read and milliseconds are normalized to seconds.
    """
    header = response.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass

    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        ms = body.get("retry_after_ms")
        if isinstance(ms, (int, float)) and not isinstance(ms, bool):
            return float(ms) / 1000.0
    return None


def _safe_detail(response: httpx.Response, limit: int = 300) -> str:
    """Short description of an error body, with the request echo stripped out.

    A 422 from Jev is FastAPI's validation format, and each entry carries an
    `input` field that echoes the request body back -- including `state`, which
    may hold personal data. Error messages end up in logs and traces, so only
    the human-readable parts are extracted and `input` is never included.
    """
    try:
        body = response.json()
    except ValueError:
        try:
            return _clip(response.text, limit)
        except Exception:  # pragma: no cover - defensive
            return "<unreadable body>"

    detail = body.get("detail", body) if isinstance(body, dict) else body

    # 422: a list of validation failures, each echoing the request in `input`.
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(p) for p in item.get("loc", []) if p != "body")
                msg = str(item.get("msg", "invalid"))
                parts.append(f"{loc}: {msg}" if loc else msg)
            else:
                parts.append(str(item))
        return _clip("; ".join(parts), limit)

    # 400/401/403: {"error_type": ..., "message": ...}
    if isinstance(detail, dict):
        message = detail.get("message")
        error_type = detail.get("error_type")
        if message:
            return _clip(f"{error_type}: {message}" if error_type else str(message), limit)
        return _clip(str(error_type or "<no message>"), limit)

    # 404 and some 400s return a bare string.
    return _clip(str(detail), limit)


def _clip(text: str, limit: int) -> str:
    return text[:limit].replace("\n", " ").strip() or "<empty body>"
