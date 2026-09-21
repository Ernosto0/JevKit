"""The Jev adapter, exercised against a mocked transport.

These tests pin the *transport* contract -- timeouts, status-code mapping,
credential hygiene -- which holds regardless of how the wire schema in
`jevkit.providers.jev.schema` is corrected in Phase 1. They deliberately do not
assert that the payload shape is correct, because it is not yet verified.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from jevkit.decisions.task import DecisionTask
from jevkit.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from jevkit.providers.base import ProviderRequest
from jevkit.providers.jev.provider import JevProvider
from jevkit.providers.jev.schema import build_request_payload, parse_response_payload

BASE_URL = "https://api.jev.test/v1"
SECRET = "sk-test-do-not-log"


def _provider() -> JevProvider:
    return JevProvider(api_key=SECRET, base_url=BASE_URL)


def _request(task: DecisionTask) -> ProviderRequest:
    return ProviderRequest(task=task, state={"message": "hi"}, timeout_seconds=2.0)


@respx.mock
async def test_successful_call_is_normalized(routing_task: DecisionTask) -> None:
    respx.post(f"{BASE_URL}/decisions").mock(
        return_value=httpx.Response(
            200,
            json={
                "decisions": {
                    "department": {"value": "billing", "probability": 0.93},
                    "urgent": {"value": 0.8, "probability": 0.8},
                },
                "model": "jev-1",
            },
        )
    )
    async with _provider() as provider:
        response = await provider.decide(_request(routing_task))

    assert response.decisions == {"department": "billing", "urgent": 0.8}
    assert response.confidence["department"] == pytest.approx(0.93)
    assert response.model == "jev-1"
    assert response.latency_ms is not None


@respx.mock
async def test_flat_response_shape_is_also_accepted(routing_task: DecisionTask) -> None:
    """The response shape is unverified, so both forms must parse."""
    respx.post(f"{BASE_URL}/decisions").mock(
        return_value=httpx.Response(200, json={"department": "billing", "urgent": 0.8})
    )
    async with _provider() as provider:
        response = await provider.decide(_request(routing_task))

    assert response.decisions["department"] == "billing"


@respx.mock
async def test_credentials_are_sent_but_never_echoed_in_errors(
    routing_task: DecisionTask,
) -> None:
    route = respx.post(f"{BASE_URL}/decisions").mock(
        return_value=httpx.Response(401, text="invalid key")
    )
    async with _provider() as provider:
        with pytest.raises(ProviderAuthError) as excinfo:
            await provider.decide(_request(routing_task))

    assert route.calls.last.request.headers["Authorization"] == f"Bearer {SECRET}"
    assert SECRET not in str(excinfo.value)


@respx.mock
async def test_timeout_maps_to_a_retryable_error(routing_task: DecisionTask) -> None:
    respx.post(f"{BASE_URL}/decisions").mock(side_effect=httpx.ReadTimeout("slow"))
    async with _provider() as provider:
        with pytest.raises(ProviderTimeoutError) as excinfo:
            await provider.decide(_request(routing_task))
    assert excinfo.value.retryable


@respx.mock
async def test_rate_limit_carries_retry_after(routing_task: DecisionTask) -> None:
    respx.post(f"{BASE_URL}/decisions").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "3"}, text="slow down")
    )
    async with _provider() as provider:
        with pytest.raises(ProviderRateLimitError) as excinfo:
            await provider.decide(_request(routing_task))

    assert excinfo.value.retry_after == 3.0
    assert excinfo.value.retryable


@respx.mock
async def test_server_error_is_retryable_but_client_error_is_not(
    routing_task: DecisionTask,
) -> None:
    respx.post(f"{BASE_URL}/decisions").mock(return_value=httpx.Response(503, text="down"))
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError) as server:
            await provider.decide(_request(routing_task))
    assert server.value.retryable

    respx.post(f"{BASE_URL}/decisions").mock(return_value=httpx.Response(400, text="bad"))
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError) as client:
            await provider.decide(_request(routing_task))
    assert not client.value.retryable


@respx.mock
async def test_non_json_body_is_a_response_error(routing_task: DecisionTask) -> None:
    respx.post(f"{BASE_URL}/decisions").mock(return_value=httpx.Response(200, text="<html>"))
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError, match="non-JSON"):
            await provider.decide(_request(routing_task))


def test_request_payload_includes_every_question(routing_task: DecisionTask) -> None:
    payload = build_request_payload(routing_task, {"message": "hi"})
    assert set(payload["questions"]) == set(routing_task.questions)
    assert payload["questions"]["department"]["options"] == [
        "billing",
        "technical",
        "account",
        "other",
    ]
    assert payload["state"] == {"message": "hi"}


def test_response_parsing_rejects_a_malformed_body() -> None:
    with pytest.raises(ProviderResponseError):
        parse_response_payload({"decisions": ["not", "a", "map"]})
    with pytest.raises(ProviderResponseError, match="no 'value'"):
        parse_response_payload({"decisions": {"department": {"probability": 0.9}}})
