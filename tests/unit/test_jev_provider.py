"""The Jev adapter, exercised against a mocked transport.

Every payload below is a real capture from the live API (jev-1.13.0,
2026-09-21), recorded by `scripts/verify_jev_api.py`. See docs/jev-api-notes.md.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from jevkit.decisions.questions import Choice, Noul, Rank, Score
from jevkit.decisions.task import DecisionTask
from jevkit.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    TaskDefinitionError,
)
from jevkit.providers.base import ProviderRequest
from jevkit.providers.jev.provider import DEFAULT_MODEL, ENDPOINT, JevProvider
from jevkit.providers.jev.schema import build_request_payload, parse_response_payload

BASE_URL = "https://api.jev.test/v1"
SECRET = "sk-test-do-not-log"
URL = f"{BASE_URL}{ENDPOINT}"

# Verbatim capture: all three question types in one request.
LIVE_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "urgent": {"type": "noul", "noul": 0.91},
        "department": {
            "type": "choice",
            "choice": "billing",
            "confidence": 1.0,
            "probabilities": {"billing": 1.0, "technical": 0.0, "account": 0.0, "other": 0.0},
        },
        "severity": {
            "type": "score",
            "score": 2.94,
            "confidence": 0.94,
            "legend": {"0": "None", "1": "Minor", "2": "Blocked", "3": "Losing money"},
            "probabilities": {"0": 0.0, "1": 0.03, "2": 0.0, "3": 0.97},
        },
    },
    "usage": {"input_tokens": 425, "output_tokens": 75},
}


def _provider(**kwargs: object) -> JevProvider:
    return JevProvider(api_key=SECRET, base_url=BASE_URL, **kwargs)  # type: ignore[arg-type]


def _request(task: DecisionTask) -> ProviderRequest:
    return ProviderRequest(task=task, state={"message": "hi"}, timeout_seconds=2.0)


def _full_task() -> DecisionTask:
    return DecisionTask(
        name="triage",
        questions={
            "urgent": Noul(instructions="Is this urgent?"),
            "department": Choice(
                instructions="Which department?",
                options=("billing", "technical", "account", "other"),
                descriptions={"billing": "Payments and refunds"},
            ),
            "severity": Score(
                instructions="How severe?",
                levels=("None", "Minor", "Blocked", "Losing money"),
            ),
        },
    )


# --------------------------------------------------------------------------
# Request shape
# --------------------------------------------------------------------------


def test_request_matches_the_verified_wire_format() -> None:
    payload = build_request_payload(_full_task(), {"message": "hi"}, model="jev-latest")

    assert payload["model"] == "jev-latest"  # required: omitting it is a 422
    assert payload["state"] == {"message": "hi"}
    assert payload["questions"]["urgent"] == {
        "type": "noul",
        "instructions": "Is this urgent?",
    }
    # `criteria`, not `options`. Undescribed options map to null, which the API accepts.
    assert payload["questions"]["department"]["criteria"] == {
        "billing": "Payments and refunds",
        "technical": None,
        "account": None,
        "other": None,
    }
    # score criteria is an ordered list of level labels.
    assert payload["questions"]["severity"]["criteria"] == [
        "None",
        "Minor",
        "Blocked",
        "Losing money",
    ]
    assert "options" not in str(payload["questions"]["department"])


def test_task_instructions_ride_on_each_question() -> None:
    """Jev has no top-level instruction slot -- sending one is a 400."""
    task = DecisionTask(
        name="triage",
        instructions="You are triaging support tickets.",
        questions={"urgent": Noul(instructions="Is this urgent?")},
    )
    payload = build_request_payload(task, {"message": "hi"}, model="jev-latest")

    assert "instructions" not in payload
    assert payload["questions"]["urgent"]["instructions"] == (
        "You are triaging support tickets.\n\nIs this urgent?"
    )


def test_unsupported_question_types_fail_before_the_network() -> None:
    task = DecisionTask(
        name="triage",
        questions={"order": Rank(instructions="Rank these", options=("a", "b"))},
    )
    with pytest.raises(TaskDefinitionError, match="Jev cannot answer"):
        build_request_payload(task, {"message": "hi"}, model="jev-latest")


def test_noul_without_instructions_is_rejected_locally() -> None:
    """The API returns 400 for this; catch it before spending a round trip."""
    task = DecisionTask(name="t", questions={"urgent": Noul()})
    with pytest.raises(TaskDefinitionError, match="needs instructions"):
        build_request_payload(task, {"message": "hi"}, model="jev-latest")


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------


def test_live_response_is_normalized() -> None:
    decisions, confidence = parse_response_payload(LIVE_RESPONSE)

    assert decisions == {"urgent": 0.91, "department": "billing", "severity": 2.94}
    assert confidence == {"department": 1.0, "severity": 0.94}
    # A noul reports no confidence field -- the probability *is* the answer.
    assert "urgent" not in confidence


def test_malformed_bodies_are_rejected() -> None:
    with pytest.raises(ProviderResponseError, match="no 'answers'"):
        parse_response_payload({"decisions": {"a": 1}})
    with pytest.raises(ProviderResponseError, match="unknown type"):
        parse_response_payload({"answers": {"a": {"type": "selection", "selection": []}}})
    with pytest.raises(ProviderResponseError, match="has no 'noul' field"):
        parse_response_payload({"answers": {"a": {"type": "noul"}}})


@respx.mock
async def test_successful_call_maps_usage_and_model() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json=LIVE_RESPONSE))
    async with _provider() as provider:
        response = await provider.decide(_request(_full_task()))

    assert response.decisions["department"] == "billing"
    assert response.model == "jev-1.13.0"
    assert response.usage is not None
    assert response.usage.input_tokens == 425
    assert response.usage.output_tokens == 75
    assert response.latency_ms is not None


@respx.mock
async def test_model_defaults_when_unconfigured() -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=LIVE_RESPONSE))
    async with _provider() as provider:
        await provider.decide(_request(_full_task()))

    assert route.calls.last.request.read().decode().count(DEFAULT_MODEL) == 1


# --------------------------------------------------------------------------
# Error mapping -- bodies are real captures
# --------------------------------------------------------------------------


@respx.mock
async def test_auth_error_does_not_echo_the_key() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(
            401,
            json={
                "detail": {
                    "error_type": "authentication_error",
                    "message": "Cannot authenticate with the server.",
                }
            },
        )
    )
    async with _provider() as provider:
        with pytest.raises(ProviderAuthError) as excinfo:
            await provider.decide(_request(_full_task()))

    assert route.calls.last.request.headers["Authorization"] == f"Bearer {SECRET}"
    assert SECRET not in str(excinfo.value)
    assert "authentication_error" in str(excinfo.value)


@respx.mock
async def test_validation_error_never_leaks_the_echoed_request() -> None:
    """A 422 echoes the request body -- including `state` -- back in `input`."""
    respx.post(URL).mock(
        return_value=httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "type": "missing",
                        "loc": ["body", "model"],
                        "msg": "Field required",
                        "input": {"state": "patient SSN 123-45-6789", "questions": {}},
                    }
                ]
            },
        )
    )
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError) as excinfo:
            await provider.decide(_request(_full_task()))

    message = str(excinfo.value)
    assert "model: Field required" in message
    assert "123-45-6789" not in message
    assert "patient SSN" not in message


@respx.mock
async def test_bare_string_detail_is_handled() -> None:
    """Some 400s return `detail` as a plain string, not an object."""
    respx.post(URL).mock(
        return_value=httpx.Response(
            400, json={"detail": "Too many score levels. Must have at most 10 levels."}
        )
    )
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError, match="at most 10 levels"):
            await provider.decide(_request(_full_task()))


@respx.mock
async def test_rate_limit_reads_retry_after_ms_from_the_body() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            429, json={"retry_after_ms": 2500, "detail": {"message": "slow down"}}
        )
    )
    async with _provider() as provider:
        with pytest.raises(ProviderRateLimitError) as excinfo:
            await provider.decide(_request(_full_task()))

    assert excinfo.value.retry_after == pytest.approx(2.5)
    assert excinfo.value.retryable


@respx.mock
async def test_rate_limit_still_honours_the_retry_after_header() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(429, headers={"Retry-After": "3"}, text="slow down")
    )
    async with _provider() as provider:
        with pytest.raises(ProviderRateLimitError) as excinfo:
            await provider.decide(_request(_full_task()))

    assert excinfo.value.retry_after == 3.0


@respx.mock
async def test_timeout_maps_to_a_retryable_error() -> None:
    respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    async with _provider() as provider:
        with pytest.raises(ProviderTimeoutError) as excinfo:
            await provider.decide(_request(_full_task()))
    assert excinfo.value.retryable


@respx.mock
async def test_overloaded_529_is_retryable_but_400_is_not() -> None:
    respx.post(URL).mock(return_value=httpx.Response(529, text="overloaded"))
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError) as server:
            await provider.decide(_request(_full_task()))
    assert server.value.retryable

    respx.post(URL).mock(
        return_value=httpx.Response(
            400, json={"detail": {"error_type": "api_usage_error", "message": "Unknown model"}}
        )
    )
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError) as client:
            await provider.decide(_request(_full_task()))
    assert not client.value.retryable


@respx.mock
async def test_non_json_body_is_a_response_error() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, text="<html>"))
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError, match="non-JSON"):
            await provider.decide(_request(_full_task()))
