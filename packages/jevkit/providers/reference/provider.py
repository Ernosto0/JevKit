"""The reference/fallback provider adapter (PLAN.md §11, Phase 3).

Calls an OpenAI-compatible Chat Completions API. `base_url` is configurable
(`JEVKIT_FALLBACK_BASE_URL`), so the same adapter also works against any other
service that implements the same endpoint shape and structured-output
contract -- this is deliberately not assumed to be "more accurate" than Jev;
its output goes through the same validation and acceptance policy as any
other provider (PLAN.md §11).
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
from jevkit.providers.reference.schema import (
    build_request_payload,
    parse_response_payload,
    parse_usage,
)

__all__ = ["DEFAULT_BASE_URL", "DEFAULT_MODEL", "ENDPOINT", "ReferenceProvider"]

ENDPOINT = "/chat/completions"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


class ReferenceProvider(ModelProvider):
    """Calls a Chat-Completions-compatible API for structured decisions.

    Supports the full provider-agnostic question vocabulary (`Noul`, `Choice`,
    `Score`, `Selection`, `Scalar`, `Rank`) via JSON-schema structured outputs,
    unlike the Jev adapter, which is limited to Jev's three question types.
    """

    name = "reference"

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
        self._api_key = api_key or cfg.require_fallback_api_key()
        self._base_url = (base_url or cfg.fallback_base_url or DEFAULT_BASE_URL).rstrip("/")
        self._model = model or cfg.fallback_model or DEFAULT_MODEL
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._auth_headers(),
            timeout=cfg.timeout_seconds,
        )

    def _auth_headers(self) -> dict[str, str]:
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
                f"Reference provider did not respond within {request.timeout_seconds}s",
                provider=self.name,
                trace_id=request.trace_id,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderResponseError(
                f"Transport error calling the reference provider: {exc}",
                provider=self.name,
                trace_id=request.trace_id,
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        self._raise_for_status(http_response, trace_id=request.trace_id)

        try:
            body: Any = http_response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                "Reference provider returned a non-JSON body",
                provider=self.name,
                status_code=http_response.status_code,
                trace_id=request.trace_id,
            ) from exc

        if not isinstance(body, dict):
            raise ProviderResponseError(
                f"Reference provider returned a JSON {type(body).__name__}, expected an object",
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
                f"Reference provider rejected the credentials ({status}): {detail}",
                provider=self.name,
                status_code=status,
                trace_id=trace_id,
            )
        if status == 429:
            raise ProviderRateLimitError(
                f"Reference provider rate limit reached: {detail}",
                retry_after=_retry_after_seconds(response),
                provider=self.name,
                status_code=status,
                trace_id=trace_id,
            )
        if status >= 500:
            error = ProviderResponseError(
                f"Reference provider server error ({status}): {detail}",
                provider=self.name,
                status_code=status,
                trace_id=trace_id,
            )
            error.retryable = True  # transient by nature
            raise error
        raise ProviderResponseError(
            f"Reference provider rejected the request ({status}): {detail}",
            provider=self.name,
            status_code=status,
            trace_id=trace_id,
        )

    async def aclose(self) -> None:
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()


def _retry_after_seconds(response: httpx.Response) -> float | None:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    return None


def _safe_detail(response: httpx.Response, limit: int = 300) -> str:
    """Short description of an error body, never the raw request echoed back."""
    try:
        body = response.json()
    except ValueError:
        try:
            return _clip(response.text, limit)
        except Exception:  # pragma: no cover - defensive
            return "<unreadable body>"

    # OpenAI-compatible shape: {"error": {"message": ..., "type": ..., "code": ...}}
    error = body.get("error") if isinstance(body, dict) else body
    if isinstance(error, dict):
        message = error.get("message")
        error_type = error.get("type") or error.get("code")
        if message:
            return _clip(f"{error_type}: {message}" if error_type else str(message), limit)
        return _clip(str(error_type or "<no message>"), limit)

    return _clip(str(error), limit)


def _clip(text: str, limit: int) -> str:
    return text[:limit].replace("\n", " ").strip() or "<empty body>"
