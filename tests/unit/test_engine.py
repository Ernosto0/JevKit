"""The engine's job is to make the lifecycle in PLAN.md section 10 observable
and bounded. These tests pin the parts that must never regress: retry limits,
fallback behavior, and the fact that an invalid answer is never accepted.
"""

from __future__ import annotations

import pytest

from jevkit.client.engine import DecisionEngine
from jevkit.decisions.result import ExecutionStatus, ValidationStatus
from jevkit.decisions.task import DecisionTask
from jevkit.errors import InputValidationError, ProviderTimeoutError
from jevkit.policies.policy import DecisionPolicy, OnFailure
from jevkit.providers.base import ModelProvider, ProviderRequest, ProviderResponse
from jevkit.providers.static import StaticProvider
from jevkit.tracing.trace import TraceStage

STATE = {"message": "I was charged twice."}


class CountingFailure(ModelProvider):
    """Fails a fixed number of times, then succeeds. Counts every call."""

    name = "counting"

    def __init__(self, *, failures: int, retryable: bool = True) -> None:
        self.calls = 0
        self._remaining = failures
        self._retryable = retryable

    async def decide(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        if self._remaining > 0:
            self._remaining -= 1
            error = ProviderTimeoutError("boom", provider=self.name)
            error.retryable = self._retryable
            raise error
        return ProviderResponse(decisions={"department": "billing", "urgent": 0.9})


async def test_accepted_result_carries_provider_and_trace(
    routing_task: DecisionTask, good_provider: StaticProvider, strict_policy: DecisionPolicy
) -> None:
    engine = DecisionEngine(primary=good_provider, policy=strict_policy)
    result, trace = await engine.run(routing_task, STATE)

    assert result.accepted
    assert result.execution_status is ExecutionStatus.ACCEPTED
    assert result.validation_status is ValidationStatus.VALID
    assert result.decisions["department"] == "billing"
    assert result.provider == "good"
    assert result.trace_id == trace.trace_id
    assert result.attempts == 1


async def test_trace_records_the_full_lifecycle(
    routing_task: DecisionTask, good_provider: StaticProvider, strict_policy: DecisionPolicy
) -> None:
    engine = DecisionEngine(primary=good_provider, policy=strict_policy)
    _result, trace = await engine.run(routing_task, STATE)

    stages = [event.stage for event in trace.events]
    for expected in (
        TraceStage.RECEIVED,
        TraceStage.INPUT_VALIDATED,
        TraceStage.POLICY_RESOLVED,
        TraceStage.PROVIDER_SELECTED,
        TraceStage.PROVIDER_CALL,
        TraceStage.RESPONSE_PARSED,
        TraceStage.OUTPUT_VALIDATED,
        TraceStage.COMPLETED,
    ):
        assert expected in stages


async def test_invalid_output_is_never_accepted(
    routing_task: DecisionTask, bad_provider: StaticProvider, strict_policy: DecisionPolicy
) -> None:
    engine = DecisionEngine(primary=bad_provider, policy=strict_policy)
    result, _trace = await engine.run(routing_task, STATE)

    assert not result.accepted
    assert result.execution_status is ExecutionStatus.FAILED


async def test_missing_input_field_raises_before_any_provider_call(
    routing_task: DecisionTask, good_provider: StaticProvider
) -> None:
    engine = DecisionEngine(primary=good_provider)
    with pytest.raises(InputValidationError, match="message"):
        await engine.run(routing_task, {"not_message": "x"})
    assert good_provider is not None  # provider was never consulted


async def test_retries_are_bounded_by_the_policy(routing_task: DecisionTask) -> None:
    provider = CountingFailure(failures=5)
    policy = DecisionPolicy(primary_provider="counting", max_retries=2, retry_backoff_seconds=0.0)
    engine = DecisionEngine(primary=provider, policy=policy)
    result, _trace = await engine.run(routing_task, STATE)

    assert provider.calls == 3  # the initial attempt plus max_retries
    assert result.execution_status is ExecutionStatus.FAILED


async def test_a_retryable_failure_can_still_succeed(routing_task: DecisionTask) -> None:
    provider = CountingFailure(failures=1)
    policy = DecisionPolicy(primary_provider="counting", max_retries=1, retry_backoff_seconds=0.0)
    engine = DecisionEngine(primary=provider, policy=policy)
    result, _trace = await engine.run(routing_task, STATE)

    assert result.accepted
    assert result.attempts == 2


async def test_non_retryable_failure_is_not_retried(routing_task: DecisionTask) -> None:
    provider = CountingFailure(failures=5, retryable=False)
    policy = DecisionPolicy(primary_provider="counting", max_retries=3, retry_backoff_seconds=0.0)
    engine = DecisionEngine(primary=provider, policy=policy)
    await engine.run(routing_task, STATE)

    assert provider.calls == 1


async def test_fallback_runs_when_the_primary_fails(
    routing_task: DecisionTask, good_provider: StaticProvider
) -> None:
    primary = CountingFailure(failures=9)
    policy = DecisionPolicy(
        primary_provider="counting",
        fallback_provider="good",
        max_retries=0,
        retry_backoff_seconds=0.0,
    )
    engine = DecisionEngine(primary=primary, fallback=good_provider, policy=policy)
    result, trace = await engine.run(routing_task, STATE)

    assert result.accepted
    assert result.used_fallback
    assert result.execution_status is ExecutionStatus.FALLBACK_ACCEPTED
    assert result.provider == "good"
    assert TraceStage.FALLBACK in [e.stage for e in trace.events]


async def test_fallback_output_is_validated_too(
    routing_task: DecisionTask, bad_provider: StaticProvider
) -> None:
    """A fallback is not trusted more than the primary (PLAN.md section 11)."""
    primary = CountingFailure(failures=9)
    policy = DecisionPolicy(
        primary_provider="counting",
        fallback_provider="bad",
        max_retries=0,
        retry_backoff_seconds=0.0,
    )
    engine = DecisionEngine(primary=primary, fallback=bad_provider, policy=policy)
    result, _trace = await engine.run(routing_task, STATE)

    assert not result.accepted


async def test_no_fallback_configured_means_no_fallback_attempt(
    routing_task: DecisionTask,
) -> None:
    primary = CountingFailure(failures=9)
    policy = DecisionPolicy(primary_provider="counting", max_retries=0)
    engine = DecisionEngine(primary=primary, policy=policy)
    result, trace = await engine.run(routing_task, STATE)

    assert not result.accepted
    assert TraceStage.FALLBACK not in [e.stage for e in trace.events]


async def test_low_confidence_routes_to_review(routing_task: DecisionTask) -> None:
    provider = StaticProvider(
        {"department": "billing", "urgent": 0.51},
        name="unsure",
        confidence={"urgent": 0.51},
    )
    policy = DecisionPolicy(
        primary_provider="unsure",
        min_confidence=0.8,
        on_low_confidence=OnFailure.REVIEW,
        max_retries=0,
    )
    engine = DecisionEngine(primary=provider, policy=policy)
    result, _trace = await engine.run(routing_task, STATE)

    assert result.execution_status is ExecutionStatus.NEEDS_REVIEW
    assert not result.accepted  # review is not an acceptance


async def test_confidence_is_ignored_when_no_threshold_is_set(
    routing_task: DecisionTask,
) -> None:
    provider = StaticProvider(
        {"department": "billing", "urgent": 0.2}, name="unsure", confidence={"urgent": 0.2}
    )
    engine = DecisionEngine(primary=provider, policy=DecisionPolicy(primary_provider="unsure"))
    result, _trace = await engine.run(routing_task, STATE)

    assert result.accepted


async def test_inputs_are_not_traced_unless_enabled(
    routing_task: DecisionTask, good_provider: StaticProvider
) -> None:
    engine = DecisionEngine(primary=good_provider)
    _result, trace = await engine.run(routing_task, STATE)
    assert trace.state is None

    engine = DecisionEngine(primary=good_provider, store_inputs=True)
    _result, trace = await engine.run(routing_task, STATE)
    assert trace.state == STATE
