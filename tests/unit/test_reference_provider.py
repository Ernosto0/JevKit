"""The reference/fallback adapter, exercised against a mocked transport.

Unlike the Jev adapter, this one is not pinned to captured payloads from a
live service -- there is no single "the reference API," only an
OpenAI-compatible Chat Completions contract. These tests pin that contract:
the JSON-schema shape sent on the request, and the response shape expected
back.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from jevkit.decisions.questions import Choice, Noul, Rank, Scalar, Score, Selection
from jevkit.decisions.task import DecisionTask
from jevkit.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from jevkit.providers.base import ProviderRequest
from jevkit.providers.reference.provider import DEFAULT_MODEL, ENDPOINT, ReferenceProvider
from jevkit.providers.reference.schema import build_request_payload, parse_response_payload

BASE_URL = "https://api.reference.test/v1"
SECRET = "sk-test-do-not-log"
URL = f"{BASE_URL}{ENDPOINT}"


def _provider(**kwargs: object) -> ReferenceProvider:
    return ReferenceProvider(api_key=SECRET, base_url=BASE_URL, **kwargs)  # type: ignore[arg-type]


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
            ),
            "severity": Score(instructions="How severe?", levels=("None", "Minor", "Blocked")),
            "tags": Selection(instructions="Pick relevant tags", options=("bug", "billing", "vip")),
            "fit": Scalar(instructions="Rate fit", minimum=0.0, maximum=10.0),
            "priority": Rank(instructions="Rank by priority", options=("a", "b", "c")),
        },
    )


def _completion(content: dict[str, object], **extra: object) -> dict[str, object]:
    return {
        "model": "gpt-4o-mini-2024-07-18",
        "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}}],
        "usage": {"prompt_tokens": 512, "completion_tokens": 64},
        **extra,
    }


# --------------------------------------------------------------------------
# Request shape
# --------------------------------------------------------------------------


def test_request_is_a_structured_output_chat_completion() -> None:
    payload = build_request_payload(_full_task(), {"message": "hi"}, model="gpt-4o-mini")

    assert payload["model"] == "gpt-4o-mini"
    assert payload["response_format"]["type"] == "json_schema"
    schema = payload["response_format"]["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(_full_task().questions)

    department = schema["properties"]["department"]["properties"]
    assert department["value"] == {
        "type": "string",
        "enum": ["billing", "technical", "account", "other"],
    }
    assert "confidence" in department  # non-noul questions ask for confidence

    urgent = schema["properties"]["urgent"]["properties"]
    assert "confidence" not in urgent  # the noul value already is the probability

    tags = schema["properties"]["tags"]["properties"]["value"]
    assert tags == {"type": "array", "items": {"type": "string", "enum": ["bug", "billing", "vip"]}}


def test_every_object_lists_all_its_properties_as_required() -> None:
    """Strict-mode structured outputs require this -- an omission is a 400."""
    payload = build_request_payload(_full_task(), {"message": "hi"}, model="gpt-4o-mini")
    schema = payload["response_format"]["json_schema"]["schema"]

    for key, prop in schema["properties"].items():
        assert set(prop["required"]) == set(prop["properties"]), key


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------


def test_valid_content_is_normalized() -> None:
    decisions, confidence = parse_response_payload(
        _completion(
            {
                "urgent": {"value": 0.8},
                "department": {"value": "billing", "confidence": 0.95},
            }
        )
    )
    assert decisions == {"urgent": 0.8, "department": "billing"}
    assert confidence == {"department": 0.95}
    assert "urgent" not in confidence


def test_refusal_is_rejected() -> None:
    body = _completion({})
    body["choices"][0]["message"] = {"role": "assistant", "refusal": "cannot comply"}  # type: ignore[index]
    with pytest.raises(ProviderResponseError, match="declined"):
        parse_response_payload(body)


def test_non_json_content_is_rejected() -> None:
    body = _completion({})
    body["choices"][0]["message"]["content"] = "not json"  # type: ignore[index]
    with pytest.raises(ProviderResponseError, match="not valid JSON"):
        parse_response_payload(body)


def test_missing_value_field_is_rejected() -> None:
    with pytest.raises(ProviderResponseError, match="no 'value' field"):
        parse_response_payload(_completion({"urgent": {"confidence": 0.5}}))


def test_missing_choices_is_rejected() -> None:
    with pytest.raises(ProviderResponseError, match="no 'choices'"):
        parse_response_payload({"usage": {}})


# --------------------------------------------------------------------------
# Provider call
# --------------------------------------------------------------------------


@respx.mock
async def test_successful_call_maps_usage_and_model() -> None:
    content = {"urgent": {"value": 0.8}, "department": {"value": "billing", "confidence": 0.9}}
    respx.post(URL).mock(return_value=httpx.Response(200, json=_completion(content)))
    task = DecisionTask(
        name="triage",
        questions={
            "urgent": Noul(instructions="Is this urgent?"),
            "department": Choice(instructions="Which?", options=("billing", "technical")),
        },
    )
    async with _provider() as provider:
        response = await provider.decide(_request(task))

    assert response.decisions == {"urgent": 0.8, "department": "billing"}
    assert response.confidence == {"department": 0.9}
    assert response.model == "gpt-4o-mini-2024-07-18"
    assert response.usage is not None
    assert response.usage.input_tokens == 512
    assert response.usage.output_tokens == 64
    assert response.latency_ms is not None


@respx.mock
async def test_model_defaults_when_unconfigured() -> None:
    body = _completion({"urgent": {"value": 0.5}})
    task = DecisionTask(name="t", questions={"urgent": Noul(instructions="Urgent?")})
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=body))
    async with _provider() as provider:
        await provider.decide(_request(task))

    assert route.calls.last.request.read().decode().count(DEFAULT_MODEL) == 1


# --------------------------------------------------------------------------
# Error mapping
# --------------------------------------------------------------------------


@respx.mock
async def test_auth_error_does_not_echo_the_key() -> None:
    error_body = {
        "error": {"message": "Incorrect API key provided", "type": "invalid_request_error"}
    }
    route = respx.post(URL).mock(return_value=httpx.Response(401, json=error_body))
    task = DecisionTask(name="t", questions={"urgent": Noul(instructions="Urgent?")})
    async with _provider() as provider:
        with pytest.raises(ProviderAuthError) as excinfo:
            await provider.decide(_request(task))

    assert route.calls.last.request.headers["Authorization"] == f"Bearer {SECRET}"
    assert SECRET not in str(excinfo.value)
    assert "invalid_request_error" in str(excinfo.value)


@respx.mock
async def test_rate_limit_honours_retry_after_header() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            429, headers={"Retry-After": "5"}, json={"error": {"message": "rate limited"}}
        )
    )
    task = DecisionTask(name="t", questions={"urgent": Noul(instructions="Urgent?")})
    async with _provider() as provider:
        with pytest.raises(ProviderRateLimitError) as excinfo:
            await provider.decide(_request(task))
    assert excinfo.value.retry_after == 5.0
    assert excinfo.value.retryable


@respx.mock
async def test_server_error_is_retryable_but_client_error_is_not() -> None:
    task = DecisionTask(name="t", questions={"urgent": Noul(instructions="Urgent?")})

    overloaded = {"error": {"message": "overloaded"}}
    respx.post(URL).mock(return_value=httpx.Response(503, json=overloaded))
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError) as server:
            await provider.decide(_request(task))
    assert server.value.retryable

    bad_schema = {"error": {"message": "bad schema"}}
    respx.post(URL).mock(return_value=httpx.Response(400, json=bad_schema))
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError) as client:
            await provider.decide(_request(task))
    assert not client.value.retryable


@respx.mock
async def test_timeout_maps_to_a_retryable_error() -> None:
    respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    task = DecisionTask(name="t", questions={"urgent": Noul(instructions="Urgent?")})
    async with _provider() as provider:
        with pytest.raises(ProviderTimeoutError) as excinfo:
            await provider.decide(_request(task))
    assert excinfo.value.retryable


@respx.mock
async def test_non_json_body_is_a_response_error() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, text="<html>"))
    task = DecisionTask(name="t", questions={"urgent": Noul(instructions="Urgent?")})
    async with _provider() as provider:
        with pytest.raises(ProviderResponseError, match="non-JSON"):
            await provider.decide(_request(task))
