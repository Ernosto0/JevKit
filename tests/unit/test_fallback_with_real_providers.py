"""Fallback exercised through two real provider adapters, not stubs.

`test_engine.py` pins the fallback *mechanics* against `StaticProvider` and a
minimal test double, which is correct and sufficient for the engine's own
logic -- it is provider-agnostic by design. This file additionally proves
that two real adapters (`JevProvider` and `ReferenceProvider`), each talking
its own wire format over its own mocked HTTP transport, actually compose
through `DecisionEngine` the same way: primary fails, fallback is validated
independently, and the result carries the fallback provider's identity.
"""

from __future__ import annotations

import json

import httpx
import respx

from jevkit.client.engine import DecisionEngine
from jevkit.decisions.questions import Choice, Noul
from jevkit.decisions.result import ExecutionStatus
from jevkit.decisions.task import DecisionTask
from jevkit.policies.policy import DecisionPolicy
from jevkit.providers.jev.provider import ENDPOINT as JEV_ENDPOINT
from jevkit.providers.jev.provider import JevProvider
from jevkit.providers.reference.provider import ENDPOINT as REFERENCE_ENDPOINT
from jevkit.providers.reference.provider import ReferenceProvider
from jevkit.tracing.trace import TraceStage

JEV_BASE_URL = "https://api.jev.test/v1"
REFERENCE_BASE_URL = "https://api.reference.test/v1"

TASK = DecisionTask(
    name="triage",
    input_fields=("message",),
    questions={
        "urgent": Noul(instructions="Is this urgent?"),
        "department": Choice(
            instructions="Which department?",
            options=("billing", "technical", "account", "other"),
        ),
    },
)
STATE = {"message": "I was charged twice."}


@respx.mock
async def test_jev_primary_falls_back_to_a_real_reference_adapter() -> None:
    # Primary (Jev) is down: every call gets a retryable server error.
    respx.post(f"{JEV_BASE_URL}{JEV_ENDPOINT}").mock(
        return_value=httpx.Response(503, json={"detail": {"message": "overloaded"}})
    )
    # Fallback (reference) answers via its own OpenAI-compatible wire format.
    reference_content = {
        "urgent": {"value": 0.72},
        "department": {"value": "billing", "confidence": 0.9},
    }
    respx.post(f"{REFERENCE_BASE_URL}{REFERENCE_ENDPOINT}").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini-2024-07-18",
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps(reference_content)}}
                ],
                "usage": {"prompt_tokens": 400, "completion_tokens": 30},
            },
        )
    )

    primary = JevProvider(api_key="jev-secret", base_url=JEV_BASE_URL)
    fallback = ReferenceProvider(api_key="ref-secret", base_url=REFERENCE_BASE_URL)
    policy = DecisionPolicy(
        primary_provider="jev",
        fallback_provider="reference",
        max_retries=0,
        retry_backoff_seconds=0.0,
    )
    engine = DecisionEngine(primary=primary, fallback=fallback, policy=policy)

    try:
        result, trace = await engine.run(TASK, STATE)
    finally:
        await primary.aclose()
        await fallback.aclose()

    assert result.accepted
    assert result.used_fallback
    assert result.execution_status is ExecutionStatus.FALLBACK_ACCEPTED
    assert result.provider == "reference"
    assert result.decisions == {"urgent": 0.72, "department": "billing"}
    assert result.confidence == {"department": 0.9}
    assert result.usage is not None
    assert result.usage.input_tokens == 400
    stages = [e.stage for e in trace.events]
    assert TraceStage.FALLBACK in stages


@respx.mock
async def test_fallback_result_is_validated_like_any_other() -> None:
    """A bad reference answer is rejected exactly like a bad primary answer."""
    respx.post(f"{JEV_BASE_URL}{JEV_ENDPOINT}").mock(
        return_value=httpx.Response(503, json={"detail": {"message": "overloaded"}})
    )
    invalid_content = {"urgent": {"value": 0.5}, "department": {"value": "not-a-real-option"}}
    respx.post(f"{REFERENCE_BASE_URL}{REFERENCE_ENDPOINT}").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": json.dumps(invalid_content)}}],
            },
        )
    )

    primary = JevProvider(api_key="jev-secret", base_url=JEV_BASE_URL)
    fallback = ReferenceProvider(api_key="ref-secret", base_url=REFERENCE_BASE_URL)
    policy = DecisionPolicy(
        primary_provider="jev",
        fallback_provider="reference",
        max_retries=0,
        retry_backoff_seconds=0.0,
    )
    engine = DecisionEngine(primary=primary, fallback=fallback, policy=policy)

    try:
        result, _trace = await engine.run(TASK, STATE)
    finally:
        await primary.aclose()
        await fallback.aclose()

    assert not result.accepted
    assert result.execution_status is ExecutionStatus.FAILED
